import asyncio
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


AMAZON_URL = "https://www.amazon.es/dp/B0C7VL6P4M"
PCCOMPONENTES_URL = "https://www.pccomponentes.com/apple-iphone-15-128gb-negro-libre"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

TIMEOUT_MS = 15_000


def parse_price(raw_price: str | None) -> Decimal | None:
    if not raw_price:
        return None

    normalized = raw_price.replace("\xa0", " ").strip()
    match = re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|\d+(?:[.,]\d{2})?)", normalized)
    if not match:
        return None

    amount = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")

    try:
        return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def serialize_price(price: Decimal | None) -> str | None:
    if price is None:
        return None

    return str(price)


async def first_visible_text(page: Page, selectors: list[str], timeout: int = TIMEOUT_MS) -> str | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            await locator.wait_for(state="visible", timeout=timeout)
            text = await locator.inner_text()
            text = " ".join(text.split())
            if text:
                return text
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return None


async def scrape_amazon(browser: Browser, url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "store": "Amazon Espana",
        "name": None,
        "price": None,
        "url": url,
        "error": None,
    }

    context = await browser.new_context(user_agent=USER_AGENT, locale="es-ES")
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        result["name"] = await first_visible_text(
            page,
            [
                "#productTitle",
                "span#productTitle",
            ],
        )
        raw_price = await first_visible_text(
            page,
            [
                "#corePrice_feature_div .a-price .a-offscreen",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                ".a-price .a-offscreen",
            ],
        )
        result["price"] = parse_price(raw_price)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await context.close()

    return result


async def scrape_pccomponentes(browser: Browser, url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "store": "PcComponentes",
        "name": None,
        "price": None,
        "url": url,
        "error": None,
    }

    context = await browser.new_context(user_agent=USER_AGENT, locale="es-ES")
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        result["name"] = await first_visible_text(
            page,
            [
                "h1",
                "[data-testid='product-title']",
                ".product-title",
            ],
        )
        raw_price = await first_visible_text(
            page,
            [
                "[data-testid='product-price']",
                "[class*='price']",
                ".precioMain",
                ".priceBlock",
            ],
        )
        result["price"] = parse_price(raw_price)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await context.close()

    return result


async def scrape_comparison(
    amazon_url: str = AMAZON_URL,
    pccomponentes_url: str = PCCOMPONENTES_URL,
) -> list[dict[str, Any]]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        try:
            return await asyncio.gather(
                scrape_amazon(browser, amazon_url),
                scrape_pccomponentes(browser, pccomponentes_url),
            )
        finally:
            await browser.close()


async def scrape_store_url(store: str, url: str) -> dict[str, Any]:
    store_key = f"{store} {url}".lower()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        try:
            if "amazon" in store_key:
                return await scrape_amazon(browser, url)

            if "pccomponentes" in store_key or "pc componentes" in store_key:
                return await scrape_pccomponentes(browser, url)

            return {
                "store": store or "unknown",
                "name": None,
                "price": None,
                "url": url,
                "error": f"Unsupported store: {store}",
            }
        finally:
            await browser.close()


def serialize_scraped_product(product: dict[str, Any]) -> dict[str, Any]:
    serialized = product.copy()
    serialized["price"] = serialize_price(serialized.get("price"))
    return serialized
