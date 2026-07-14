import json
import logging
import os
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from scraper.scrapers import scrape_search_all
from services.matching import group_by_family
from services.persistence import LinkUpdate, persist_family
from services.predictor import classify_best_moment, decimal_to_money, load_product_price_history


logger = logging.getLogger(__name__)

# A search launches 4 headless-browser contexts against real store pages, easily
# the most expensive and most bot-detectable part of a request - caching the
# whole response for repeated keywords avoids re-scraping every store on every
# request within this window, and reduces load/ban risk against the stores.
SEARCH_CACHE_TTL_SECONDS = 900

_redis_client: Redis | None = None


def _get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _cache_key(keyword: str) -> str:
    return f"trendbuy:search:{keyword.strip().lower()}"


def _discount_percent(previous_price: Decimal | None, current_price: Decimal) -> Decimal:
    if previous_price is None or previous_price <= 0:
        return Decimal("0.00")

    return ((previous_price - current_price) / previous_price * Decimal("100")).quantize(Decimal("0.01"))


def _cheapest_update(updates: list[LinkUpdate]) -> LinkUpdate:
    return min(updates, key=lambda update: update.current_price)


async def search_products(session: AsyncSession, keyword: str) -> dict[str, Any]:
    redis_client = _get_redis()
    cache_key = _cache_key(keyword)

    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception as exc:
        # Redis being unavailable must never break search, only skip the cache.
        logger.warning("Search cache read failed for keyword=%r: %s", keyword, exc)

    raw_items = await scrape_search_all(keyword)
    families = group_by_family(raw_items)

    payloads: list[dict[str, Any]] = []

    for family_items in families:
        canonical_name = max(
            (item["name"] for item in family_items if item.get("name")),
            key=len,
            default=keyword,
        )
        producto, updates = await persist_family(session, family_items, canonical_name)

        if not updates:
            continue

        history = await load_product_price_history(session, producto.id)
        best_moment = classify_best_moment(history)
        historic_min = best_moment.get("historic_min")

        cheapest = _cheapest_update(updates)
        # A product seen for the first time has a single price point, so its
        # historic_min equals its current price and this reads as historic-low
        # trivially — same behavior classify_best_moment already has today.
        is_historic_low = historic_min is not None and cheapest.current_price <= Decimal(historic_min)
        discount_percent = _discount_percent(cheapest.previous_price, cheapest.current_price)

        stores = sorted(
            (
                {
                    "store": update.enlace.tienda,
                    "price": decimal_to_money(update.current_price),
                    "url": update.enlace.url,
                }
                for update in updates
            ),
            key=lambda store: Decimal(store["price"]),
        )

        payloads.append(
            {
                "product_id": producto.id,
                "name": producto.nombre,
                "is_historic_low": is_historic_low,
                "best_status": best_moment.get("status"),
                "discount_percent": str(discount_percent),
                "stores": stores,
            }
        )

    await session.commit()

    payloads.sort(key=lambda family: (not family["is_historic_low"], -Decimal(family["discount_percent"])))

    response = {"query": keyword, "families": payloads}

    try:
        await redis_client.set(cache_key, json.dumps(response), ex=SEARCH_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Search cache write failed for keyword=%r: %s", keyword, exc)

    return response
