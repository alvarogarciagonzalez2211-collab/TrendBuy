import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


AMAZON_URL = "https://www.amazon.es/dp/B0C7VL6P4M"
PCCOMPONENTES_URL = "https://www.pccomponentes.com/apple-iphone-15-128gb-negro-libre"

AMAZON_SEARCH_URL = "https://www.amazon.es/s?k={query}"
PCCOMPONENTES_SEARCH_URL = "https://www.pccomponentes.com/search?query={query}"
MEDIAMARKT_SEARCH_URL = "https://www.mediamarkt.es/es/search.html?query={query}"
WORTEN_SEARCH_URL = "https://www.worten.es/search?query={query}"
IKEA_SEARCH_URL = "https://www.ikea.com/es/es/search/?q={query}"
VINTED_SEARCH_URL = "https://www.vinted.es/catalog?search_text={query}"
DRUNI_HOME_URL = "https://www.druni.es/"

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


def parse_jsonld_price(raw: Any) -> Decimal | None:
    # JSON-LD prices use machine formatting ("659.99", 659.99), NOT the es-ES
    # human formatting parse_price() handles - '.' is the decimal separator
    # here, so parse_price would misread "1439.00" as 143900.
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        raw = str(raw)

    if not isinstance(raw, str):
        return None

    cleaned = raw.replace("\xa0", " ").strip().replace("€", "").replace("EUR", "").strip()
    # Tolerate a stray es-ES-formatted value (comma decimals) some stores put
    # in their JSON-LD anyway: a comma after the last dot must be the decimal.
    if "," in cleaned and cleaned.rfind(",") > cleaned.rfind("."):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        price = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    return price if price > 0 else None


def _iter_jsonld_nodes(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _iter_jsonld_nodes(item)
    elif isinstance(node, dict):
        yield node
        # @graph is how many storefronts (Magento, WooCommerce...) nest the
        # Product next to Organization/BreadcrumbList in a single script tag.
        yield from _iter_jsonld_nodes(node.get("@graph"))


def _offer_price(offers: Any) -> Decimal | None:
    prices = []
    for offer in offers if isinstance(offers, list) else [offers]:
        if not isinstance(offer, dict):
            continue
        # AggregateOffer carries lowPrice; a plain Offer carries price. Some
        # stores also nest priceSpecification - covered by the price key
        # fallback chain here.
        for key in ("lowPrice", "price"):
            price = parse_jsonld_price(offer.get(key))
            if price is not None:
                prices.append(price)
                break
        else:
            spec = offer.get("priceSpecification")
            if isinstance(spec, dict):
                price = parse_jsonld_price(spec.get("price"))
                if price is not None:
                    prices.append(price)
    return min(prices) if prices else None


def extract_jsonld_product(payloads: list[str]) -> dict[str, Any] | None:
    # Pure function (unit-tested, no Playwright) that turns the raw contents
    # of a page's <script type="application/ld+json"> tags into {name, price}.
    # schema.org Product markup is the closest thing e-commerce has to a
    # universal API: one extractor covers product pages on most stores without
    # per-store selectors that rot.
    for payload in payloads:
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue

        for node in _iter_jsonld_nodes(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if not any(isinstance(t, str) and t.lower() == "product" for t in types):
                continue

            price = _offer_price(node.get("offers"))
            if price is None:
                continue

            name = node.get("name")
            image = node.get("image")
            if isinstance(image, list):
                image = image[0] if image else None
            if isinstance(image, dict):
                image = image.get("url")

            return {
                "name": " ".join(str(name).split()) if name else None,
                "price": price,
                "image_url": image if isinstance(image, str) else None,
            }

    return None


async def scrape_generic_product(browser: Browser, url: str, store: str | None = None) -> dict[str, Any]:
    # Detail scraper for every store WITHOUT a hand-tuned scrape_* above -
    # this is what lets the 12h Celery refresh and "seguir por URL" work for
    # any store the keyword search can discover, instead of only the original
    # four. Strategy: JSON-LD first (near-universal), schema.org microdata
    # (itemprop) second, visible-text price parsing deliberately NOT attempted
    # (too error-prone without per-store verification).
    display_store = store or store_display_name_for_url(url)
    result: dict[str, Any] = {
        "store": display_store,
        "name": None,
        "price": None,
        "url": url,
        "error": None,
    }

    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        # JSON-LD scripts are injected by the server or early hydration; give
        # client-rendered pages one short beat to attach them.
        await page.wait_for_timeout(1_000)

        payloads = await page.locator("script[type='application/ld+json']").all_inner_texts()
        product = extract_jsonld_product(payloads)

        if product is not None:
            result["name"] = product["name"]
            result["price"] = product["price"]
        else:
            try:
                raw_price = await page.locator("[itemprop='price']").first.get_attribute(
                    "content", timeout=CARD_TIMEOUT_MS
                )
                result["price"] = parse_jsonld_price(raw_price)
            except Exception:
                result["price"] = None

            if result["price"] is not None:
                result["name"] = await first_visible_text(page, ["h1"], timeout=CARD_TIMEOUT_MS)

        if result["price"] is None:
            result["error"] = "No structured price data (JSON-LD/microdata) found on page"
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

            try:
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "Amazon Espana",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
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

            try:
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "PcComponentes",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
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

            try:
                # The card also carries a small badge image (energy label) after
                # the product photo - .first is the product photo, confirmed
                # live against real MediaMarkt search results (2026-07-14).
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "MediaMarkt",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

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

            try:
                # Worten serves image src as a site-relative path ("/i/...."),
                # unlike the other 3 stores which return an absolute URL.
                raw_image = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                raw_image = None
            image_url = urljoin(url, raw_image) if raw_image else None

            price = parse_price(raw_price) if raw_price else None
            product_url = urljoin(url, href) if href else None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "Worten",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_ikea(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = IKEA_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # Each card carries its own name/price as data attributes too, but those
        # are meant for IKEA's own JS (unconfirmed decimal-separator convention) -
        # the rendered price module text goes through the same cheapest_price_in()
        # parser already trusted (and pytest-covered) for every other store here,
        # so results stay consistent regardless of how IKEA formats that attribute.
        cards = page.locator("[data-testid=plp-product-card]")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                # IKEA's second product image carries a short, clean "<line>
                # <type>, <color>" alt (e.g. "ROSENTORP Silla, blanco"), but it
                # only attaches once the lazy-loaded image itself resolves - the
                # stealth context blocks image requests (see BLOCKED_RESOURCE_TYPES),
                # so that element never appears live. The first (eager-loaded)
                # image's alt is a longer full-sentence description but is always
                # present regardless of the image request being blocked.
                name = await card.locator("img").first.get_attribute("alt", timeout=CARD_TIMEOUT_MS)
                name = " ".join(name.split()) if name else None
            except Exception:
                name = None
            if not name:
                continue

            try:
                price_text = await card.locator(".plp-price-module__price").first.inner_text(
                    timeout=CARD_TIMEOUT_MS
                )
                price = cheapest_price_in(price_text)
            except Exception:
                price = None

            try:
                href = await card.locator("a").first.get_attribute("href", timeout=CARD_TIMEOUT_MS)
                product_url = urljoin(url, href) if href else None
            except Exception:
                product_url = None

            try:
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "IKEA",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_vinted(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = VINTED_SEARCH_URL.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        cards = page.locator("div.new-item-box__container")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            try:
                # Vinted has no separate title element in the compact grid card -
                # the full listing title lives in the overlay link's title attr,
                # bundled with brand/condition/size/price ("Camiseta X, marca: Y,
                # estado: Z, ... 1,90 e"). Cutting at the first "marca:"/"estado:"
                # marker isolates just the title, confirmed live against real cards.
                raw_title = await card.locator("a.new-item-box__overlay--clickable").first.get_attribute(
                    "title", timeout=CARD_TIMEOUT_MS
                )
                href = await card.locator("a.new-item-box__overlay--clickable").first.get_attribute(
                    "href", timeout=CARD_TIMEOUT_MS
                )
            except Exception:
                continue

            name = None
            if raw_title:
                marker = re.search(r",\s*(marca|estado):", raw_title)
                name = raw_title[: marker.start()] if marker else raw_title
                name = " ".join(name.split())

            try:
                # Scoped to the summary block only - the card also shows an
                # unrelated leading digit (a "liked by N people" style badge)
                # right before the brand line that would otherwise get parsed
                # as a bogus price by cheapest_price_in() on the full card text.
                price_text = await card.locator("div.new-item-box__summary").first.inner_text(
                    timeout=CARD_TIMEOUT_MS
                )
                price = cheapest_price_in(price_text)
            except Exception:
                price = None

            try:
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            product_url = urljoin(url, href) if href else None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "Vinted",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


async def search_druni(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        # Druni has no working direct search URL (both a Magento-style
        # /catalogsearch/result/ and a plain /buscar path were tried live and
        # returned 406/404) - only driving its own search box like a real user
        # reaches real results, which then render as a client-side overlay
        # instead of navigating to a new URL.
        await page.goto(DRUNI_HOME_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.wait_for_timeout(1000)

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

        search_input = page.locator("input[type=search]").first
        try:
            await search_input.wait_for(state="visible", timeout=TIMEOUT_MS)
            # A geoip popup (x-data="initGeoipPopup()") stays in the DOM and
            # intercepts pointer events even once it's no longer visually
            # present - confirmed live, a plain click() times out waiting for
            # it to stop blocking. force=True skips that actionability check;
            # fill() still requires the element to genuinely be editable, so
            # this can't silently type into the wrong place.
            await search_input.click(timeout=CARD_TIMEOUT_MS, force=True)
            await search_input.fill(keyword, timeout=CARD_TIMEOUT_MS)
            await search_input.press("Enter")
        except Exception:
            return []

        cards = page.locator("form.product-item")
        try:
            await cards.first.wait_for(state="attached", timeout=TIMEOUT_MS)
        except Exception:
            return []
        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []
        current_url = page.url

        for index in range(count):
            card = cards.nth(index)

            try:
                brand = await card.locator("p.product-brand").first.inner_text(timeout=CARD_TIMEOUT_MS)
            except Exception:
                brand = ""

            try:
                title = await card.locator("span.product-card-title").first.inner_text(timeout=CARD_TIMEOUT_MS)
            except Exception:
                title = None

            name = " ".join(f"{brand} {title}".split()) if title else None
            if not name:
                continue

            try:
                price_text = await card.locator("div.price-box.price-final_price").first.inner_text(
                    timeout=CARD_TIMEOUT_MS
                )
                price = cheapest_price_in(price_text)
            except Exception:
                price = None

            try:
                href = await card.locator("a.product-item-link").first.get_attribute(
                    "href", timeout=CARD_TIMEOUT_MS
                )
                product_url = urljoin(current_url, href) if href else None
            except Exception:
                product_url = None

            try:
                image_url = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                image_url = None

            if not name or price is None or not product_url:
                continue

            items.append(
                {
                    "store": "Druni",
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


@dataclass
class StoreSearchConfig:
    # Declarative recipe for the long tail of stores: the four hand-written
    # search_* functions above earned their special-casing through live
    # debugging; every store after them shares the same shape (grid of cards,
    # name/price/link inside each card) and only differs in selectors. Each
    # selector field is a fallback chain - first match wins - so a store
    # redesign degrades gracefully instead of instantly breaking.
    store: str
    search_url: str  # str.format with {query}
    card_selectors: list[str]
    name_selectors: list[str]
    price_selectors: list[str]
    link_selectors: list[str] = field(default_factory=lambda: ["a"])


async def _first_inner_text(card, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            text = await card.locator(selector).first.inner_text(timeout=CARD_TIMEOUT_MS)
            text = " ".join(text.split())
            if text:
                return text
        except Exception:
            continue
    return None


async def _first_href(card, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            href = await card.locator(selector).first.get_attribute("href", timeout=CARD_TIMEOUT_MS)
            if href:
                return href
        except Exception:
            continue
    return None


async def search_store_by_config(browser: Browser, keyword: str, config: StoreSearchConfig) -> list[dict[str, Any]]:
    context = await new_stealth_context(browser)
    page = await context.new_page()

    try:
        url = config.search_url.format(query=quote(keyword))
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        cards = None
        for card_selector in config.card_selectors:
            candidate = page.locator(card_selector)
            try:
                await candidate.first.wait_for(state="attached", timeout=TIMEOUT_MS)
                cards = candidate
                break
            except Exception:
                continue
        if cards is None:
            return []

        count = min(await cards.count(), SEARCH_RESULT_LIMIT)
        items: list[dict[str, Any]] = []

        for index in range(count):
            card = cards.nth(index)

            name = await _first_inner_text(card, config.name_selectors)
            if not name:
                continue

            price_text = await _first_inner_text(card, config.price_selectors)
            price = cheapest_price_in(price_text)

            href = await _first_href(card, config.link_selectors)
            product_url = urljoin(url, href) if href else None

            try:
                raw_image = await card.locator("img").first.get_attribute("src", timeout=CARD_TIMEOUT_MS)
            except Exception:
                raw_image = None
            image_url = urljoin(url, raw_image) if raw_image else None

            if price is None or not product_url:
                continue

            items.append(
                {
                    "store": config.store,
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "image_url": image_url,
                    "error": None,
                }
            )

        return items
    except Exception:
        return []
    finally:
        await context.close()


# ⚠️ NOT yet verified against live pages (this dev environment has no outbound
# network access to the stores - 2026-07-15). Selectors are best-effort from
# each platform's known storefront (Decathlon's design system, Salesforce
# Commerce Cloud for Sprinter, Magento for Primor). Every one of them fails
# SOFT (empty result list, search continues with the other stores), and the
# generic JSON-LD detail scraper - which does not depend on these selectors -
# still covers their product pages for URL-tracking and refreshes. To verify:
# run a live search per store and check items come back with sane prices;
# fix selectors against the real DOM if not (same process used for the
# original four, see CLAUDE.md).
DECATHLON_SEARCH = StoreSearchConfig(
    store="Decathlon",
    search_url="https://www.decathlon.es/es/search?Ntt={query}",
    card_selectors=["[data-testid='product-card']", "article[class*='product']", "div.dpb-holder"],
    name_selectors=["[data-testid='product-card-title']", "h2", "[class*='title']"],
    price_selectors=["[data-testid='price']", "[class*='price']"],
)

SPRINTER_SEARCH = StoreSearchConfig(
    store="Sprinter",
    search_url="https://www.sprintersports.com/buscador?q={query}",
    card_selectors=["div.product-tile", "div.product", "[class*='product-card']"],
    name_selectors=["a.link", ".pdp-link", "[class*='name']", "h2", "h3"],
    price_selectors=[".price .sales .value", ".price", "[class*='price']"],
)

PRIMOR_SEARCH = StoreSearchConfig(
    store="Primor",
    search_url="https://www.primor.eu/es_es/catalogsearch/result/?q={query}",
    card_selectors=["li.item.product.product-item", "li.product-item", "[class*='product-item']"],
    name_selectors=["a.product-item-link", ".product-item-name", "h2", "h3"],
    price_selectors=[".price-box", "[class*='price']"],
    link_selectors=["a.product-item-link", "a"],
)

CASADELLIBRO_SEARCH = StoreSearchConfig(
    store="Casa del Libro",
    search_url="https://www.casadellibro.com/busqueda-generica?busqueda={query}",
    card_selectors=["[class*='compact-product']", "[class*='product-card']", "article"],
    name_selectors=["h2", "h3", "[class*='title']"],
    price_selectors=["[class*='price']"],
)


async def search_decathlon(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    return await search_store_by_config(browser, keyword, DECATHLON_SEARCH)


async def search_sprinter(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    return await search_store_by_config(browser, keyword, SPRINTER_SEARCH)


async def search_primor(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    return await search_store_by_config(browser, keyword, PRIMOR_SEARCH)


async def search_casadellibro(browser: Browser, keyword: str) -> list[dict[str, Any]]:
    return await search_store_by_config(browser, keyword, CASADELLIBRO_SEARCH)


# Coarse routing taxonomy, deliberately separate from services.categories'
# CATEGORY_KEYWORDS: that one is fine-grained (8 categories) for tagging
# already-found products for favorites; this one only has to decide, before
# any scraping happens, which store set a raw query keyword belongs to - a
# handful of broad sections is enough and keeps scraper/ free of a dependency
# on services/ (services/search.py already depends on scraper/, not the other
# way round).
STORE_SECTION_KEYWORDS: dict[str, list[str]] = {
    "ropa": [
        "camiseta", "pantalon", "vaquero", "jean", "sudadera", "chaqueta", "vestido",
        "falda", "jersey", "abrigo", "camisa", "zapatilla", "calzado", "zapato",
        "ropa", "moda", "polo", "bermuda", "chandal", "bufanda", "gorro", "bolso",
    ],
    "hogar": [
        "silla", "sofa", "mesa", "estanteria", "armario", "colchon", "lampara",
        "mueble", "cortina", "alfombra", "cojin", "espejo", "escritorio", "cama",
        "decoracion",
    ],
    "belleza": [
        "crema", "perfume", "maquillaje", "champu", "cosmetica", "serum",
        "protector solar", "colonia", "mascarilla facial", "labial", "gel de ducha",
        "belleza",
    ],
    "deportes": [
        "bicicleta", "mancuerna", "cinta de correr", "raqueta", "balon", "futbol",
        "padel", "esqui", "camping", "tienda de campana", "patinete", "deporte",
        "fitness", "yoga", "gimnasio", "running", "senderismo", "montana", "surf",
        "natacion", "esterilla", "mochila",
    ],
    "libros": [
        "libro", "novela", "comic", "manga", "cuento", "trilogia", "saga",
        "bestseller", "libreria",
    ],
}

# Amazon is a broad marketplace relevant to every section, so it always runs.
# PcComponentes/MediaMarkt/Worten are tech-focused - they only make sense for a
# recognized tech query or, to preserve the original behavior for anything this
# taxonomy doesn't recognize, as the default when no section matches at all.
ALWAYS_SCRAPERS = [search_amazon]
TECH_ONLY_SCRAPERS = [search_pccomponentes, search_mediamarkt, search_worten]
SECTION_SCRAPERS = {
    # Sprinter covers sportswear/sneakers, a big share of real "ropa" queries.
    "ropa": [search_vinted, search_sprinter],
    # MediaMarkt/Worten already sell home appliances, on top of IKEA for furniture.
    "hogar": [search_ikea, search_mediamarkt, search_worten],
    "belleza": [search_druni, search_primor],
    "deportes": [search_decathlon, search_sprinter],
    "libros": [search_casadellibro],
}


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def detect_store_sections(keyword: str) -> list[str]:
    normalized = _strip_accents(keyword.lower())
    return [section for section, kws in STORE_SECTION_KEYWORDS.items() if any(kw in normalized for kw in kws)]


def resolve_search_scrapers(keyword: str) -> list[Any]:
    sections = detect_store_sections(keyword)
    scrapers = list(ALWAYS_SCRAPERS)
    if not sections:
        scrapers.extend(TECH_ONLY_SCRAPERS)
    else:
        for section in sections:
            scrapers.extend(SECTION_SCRAPERS[section])

    seen: set[int] = set()
    unique_scrapers = []
    for fn in scrapers:
        if id(fn) not in seen:
            seen.add(id(fn))
            unique_scrapers.append(fn)
    return unique_scrapers


async def scrape_search_all(keyword: str) -> list[dict[str, Any]]:
    scrapers = resolve_search_scrapers(keyword)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        try:
            store_results = await asyncio.gather(
                *(fn(browser, keyword) for fn in scrapers),
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


# Single source of truth for "which stores does TrendBuy know" - keyed by the
# distinctive hostname fragment, valued with the display name used everywhere
# a store is shown to a user. services/search.py derives its supported-URL
# check from this, so adding a store here automatically enables track-by-URL
# for it (detail scraping falls back to scrape_generic_product below).
KNOWN_STORES: dict[str, str] = {
    "amazon": "Amazon Espana",
    "pccomponentes": "PcComponentes",
    "mediamarkt": "MediaMarkt",
    "worten": "Worten",
    "ikea": "IKEA",
    "vinted": "Vinted",
    "druni": "Druni",
    "decathlon": "Decathlon",
    "sprinter": "Sprinter",
    "primor": "Primor",
    "casadellibro": "Casa del Libro",
}


def store_display_name_for_url(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    for marker, display_name in KNOWN_STORES.items():
        if marker in host:
            return display_name
    return host or "unknown"


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

            # Everything else (IKEA/Vinted/Druni/Decathlon/... and whatever
            # comes next) goes through structured-data extraction - this is
            # what keeps the 12h price refresh working for stores that only
            # have a search scraper, instead of their history silently never
            # growing past the first data point.
            return await scrape_generic_product(browser, url, store or None)
        finally:
            await browser.close()


def serialize_scraped_product(product: dict[str, Any]) -> dict[str, Any]:
    serialized = product.copy()
    serialized["price"] = serialize_price(serialized.get("price"))
    return serialized
