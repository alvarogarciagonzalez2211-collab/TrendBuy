import asyncio
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote, urljoin

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


AMAZON_URL = "https://www.amazon.es/dp/B0C7VL6P4M"
PCCOMPONENTES_URL = "https://www.pccomponentes.com/apple-iphone-15-128gb-negro-libre"

AMAZON_SEARCH_URL = "https://www.amazon.es/s?k={query}"
PCCOMPONENTES_SEARCH_URL = "https://www.pccomponentes.com/search?query={query}"
MEDIAMARKT_SEARCH_URL = "https://www.mediamarkt.es/es/search.html?query={query}"
WORTEN_SEARCH_URL = "https://www.worten.es/search?query={query}"

SEARCH_RESULT_LIMIT = 20

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

TIMEOUT_MS = 15_000
# Playwright locators auto-wait/retry up to their timeout before failing, even
# for a plain existence check. Reusing TIMEOUT_MS (sized for a full page
# navigation) inside a per-card loop means a single sponsored/malformed card
# with no matching sub-element burns a full 15s before search_* moves on to the
# next card - with ~20 cards x 3 locator calls that made one live search take
# several minutes. Card-level lookups only need to wait out client-side
# rendering, not a network round trip, so they get a much shorter budget.
CARD_TIMEOUT_MS = 2_000

# Verified live (2026-07-14) against Amazon.es / PcComponentes / MediaMarkt.es /
# Worten.es real search pages. El Corte Ingles and Fnac were dropped after live
# testing: both return a hard 403 "Access Denied" from their WAF (Akamai/PerimeterX
# -style bot management) even with the stealth context below - not a selector
# problem, a network-level block that isn't worth fighting with proxy rotation for
# this project's scope. Worten replaces them and was verified reachable + scrapable.
BLOCKED_RESOURCE_TYPES = {"image", "font", "media"}


async def new_stealth_context(browser: Browser):
    context = await browser.new_context(user_agent=USER_AGENT, locale="es-ES", viewport={"width": 1366, "height": 900})
    # Cuts page weight substantially (images/fonts/media aren't needed to read
    # name+price+link out of a results grid) and reduces the odds of tripping
    # bandwidth-based bot heuristics.
    await context.route(
        lambda url: True,
        lambda route: route.abort()
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES
        else route.continue_(),
    )
    # A minimal but real signal several store WAFs check for; doesn't defeat a
    # dedicated Akamai/PerimeterX challenge (see El Corte Ingles/Fnac above) but
    # measurably helps against lighter bot checks.
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    return context


# Spanish/European formatting only ('.' = thousands separator, ',' = decimal
# separator) - matches the es-ES locale used everywhere in this project. The
# decimal group is optional so whole-euro prices with no visible decimals (very
# common in search-result cards, e.g. "1.439€") parse correctly instead of
# silently losing digits to the thousands separator.
PRICE_TOKEN_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?")

# Search-result price containers often bundle the real price together with a
# discount badge ("-15%") and/or a monthly financing figure ("52,26 €/mes") in
# the same block of text - both match PRICE_TOKEN_RE just as well as a real
# price, so line-level filtering happens in parse_price_lines() before any
# individual line is handed to parse_price().
PRICE_LINE_EXCLUDE_RE = re.compile(r"%|/\s*mes\b|\bmes\b", re.IGNORECASE)


def parse_price(raw_price: str | None) -> Decimal | None:
    if not raw_price:
        return None

    normalized = raw_price.replace("\xa0", " ").strip()
    match = PRICE_TOKEN_RE.search(normalized)
    if not match:
        return None

    amount = match.group(0).replace(".", "").replace(",", ".")

    try:
        return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def parse_price_lines(raw_text: str | None) -> list[Decimal]:
    if not raw_text:
        return []

    prices: list[Decimal] = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line or PRICE_LINE_EXCLUDE_RE.search(line):
            continue
        price = parse_price(line)
        if price is not None:
            prices.append(price)

    return prices


def cheapest_price_in(raw_text: str | None) -> Decimal | None:
    # The current selling price is always <= any struck-through original price
    # shown alongside it, regardless of which one appears first in the DOM (MediaMarkt
    # lists the struck price first, PcComponentes lists the current price first) -
    # so taking the minimum of the surviving lines is order-independent and safe.
    prices = parse_price_lines(raw_text)
    return min(prices) if prices else None


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

    context = await new_stealth_context(browser)
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

    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        result["name"] = await first_visible_text(
            page,
            [
                "h1.product-card__title",
                "h1",
                "[data-testid='product-title']",
            ],
        )
        raw_price_text = await first_visible_text(
            page,
            [
                "div.product-card__price-container",
                "[data-testid='product-price']",
                "[class*='price']",
            ],
        )
        result["price"] = cheapest_price_in(raw_price_text) or parse_price(raw_price_text)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await context.close()

    return result


async def scrape_mediamarkt(browser: Browser, url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "store": "MediaMarkt",
        "name": None,
        "price": None,
        "url": url,
        "error": None,
    }

    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        result["name"] = await first_visible_text(
            page,
            [
                "[data-test='product-title']",
                "h1",
            ],
        )
        raw_price_text = await first_visible_text(
            page,
            [
                "[data-test='mms-price']",
                "[class*='price']",
            ],
        )
        result["price"] = cheapest_price_in(raw_price_text) or parse_price(raw_price_text)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await context.close()

    return result


async def scrape_worten(browser: Browser, url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "store": "Worten",
        "name": None,
        "price": None,
        "url": url,
        "error": None,
    }

    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        result["name"] = await first_visible_text(page, ["h1"])

        # Worten exposes the current price as schema.org Product/Offer microdata
        # (<meta itemprop="price" content="659.99">) - more reliable than parsing
        # rendered text, and confirmed live to match the search-result price.
        try:
            raw_price = await page.locator("[itemprop='price']").first.get_attribute(
                "content", timeout=TIMEOUT_MS
            )
            result["price"] = parse_price(raw_price)
        except Exception:
            result["price"] = None
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await context.close()

    return result


async def search_amazon(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = AMAZON_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        cards = page.locator("[data-component-type='s-search-result']")
        # locator.count() is a synchronous DOM snapshot, it does NOT auto-wait like
        # other locator actions - calling it right after "domcontentloaded" on a
        # client-rendered results grid races the page's own JS and silently
        # returns 0 whenever hydration hasn't finished yet. Waiting for the first
        # card to attach first makes this deterministic instead of "sometimes
        # works depending on how fast the SPA renders".
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                name_text = await card.locator("h2 span").first.inner_text(timeout=CARD_TIMEOUT_MS)
                name = " ".join(name_text.split())
            except Exception:
                continue

            try:
                price_text = await card.locator(".a-price .a-offscreen").first.inner_text(timeout=CARD_TIMEOUT_MS)
                price = parse_price(price_text)
            except Exception:
                price = None

            try:
                href = await card.locator("a[href*='/dp/']").first.get_attribute("href", timeout=CARD_TIMEOUT_MS)
                product_url = urljoin(url, href) if href else None
            except Exception:
                product_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {"store": "Amazon Espana", "name": name, "price": price, "url": product_url, "error": None}
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_pccomponentes(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = PCCOMPONENTES_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        cards = page.locator("div.product-card")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                name_text = await card.locator("h3.product-card__title").first.inner_text(timeout=CARD_TIMEOUT_MS)
                name = " ".join(name_text.split())
            except Exception:
                continue

            try:
                price_text = await card.locator("div.product-card__price-container").first.inner_text(
                    timeout=CARD_TIMEOUT_MS
                )
                price = cheapest_price_in(price_text)
            except Exception:
                price = None

            try:
                # The card itself is nested INSIDE the product link (its parent
                # is the <a>), not the other way around - "a" as a descendant
                # selector never matches and silently times out on every card.
                href = await card.locator("xpath=ancestor::a[1]").first.get_attribute(
                    "href", timeout=CARD_TIMEOUT_MS
                )
                product_url = urljoin(url, href) if href else None
            except Exception:
                product_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {"store": "PcComponentes", "name": name, "price": price, "url": product_url, "error": None}
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_mediamarkt(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = MEDIAMARKT_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        cards = page.locator("[data-test='mms-product-card']")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                name_text = await card.locator("[data-test='product-title']").first.inner_text(
                    timeout=CARD_TIMEOUT_MS
                )
                name = " ".join(name_text.split())
            except Exception:
                continue

            try:
                price_text = await card.locator("[data-test='mms-price']").first.inner_text(timeout=CARD_TIMEOUT_MS)
                price = cheapest_price_in(price_text)
            except Exception:
                price = None

            try:
                href = await card.locator("[data-test='product-list-item-link']").first.get_attribute(
                    "href", timeout=CARD_TIMEOUT_MS
                )
                product_url = urljoin(url, href) if href else None
            except Exception:
                product_url = None

            if not name or price is None or not product_url:
                continue

            items.append({"store": "MediaMarkt", "name": name, "price": price, "url": product_url, "error": None})

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_worten(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = WORTEN_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # Worten's cards carry name/price as data attributes (Constructor.io
        # tracking) directly on the card element - more reliable than parsing
        # rendered text, confirmed live against real search results.
        cards = page.locator("article.product-card")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                name = await card.get_attribute("data-cnstrc-item-name", timeout=CARD_TIMEOUT_MS)
                raw_price = await card.get_attribute("data-cnstrc-item-price", timeout=CARD_TIMEOUT_MS)
                href = await card.locator("a").first.get_attribute("href", timeout=CARD_TIMEOUT_MS)
            except Exception:
                continue

            price = parse_price(raw_price) if raw_price else None
            product_url = urljoin(url, href) if href else None

            if not name or price is None or not product_url:
                continue

            items.append({"store": "Worten", "name": name, "price": price, "url": product_url, "error": None})

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def scrape_search_all(keyword: str) -> list[dict[str, Any]]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        try:
            store_results = await asyncio.gather(
                search_amazon(browser, keyword),
                search_pccomponentes(browser, keyword),
                search_mediamarkt(browser, keyword),
                search_worten(browser, keyword),
                return_exceptions=True,
            )
        finally:
            await browser.close()

    flattened: list[dict[str, Any]] = []
    for result in store_results:
        if isinstance(result, Exception):
            continue
        flattened.extend(result)

    return flattened


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

            if "mediamarkt" in store_key or "media markt" in store_key:
                return await scrape_mediamarkt(browser, url)

            if "worten" in store_key:
                return await scrape_worten(browser, url)

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
