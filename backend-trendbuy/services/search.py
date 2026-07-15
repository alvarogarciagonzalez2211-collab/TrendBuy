import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Busqueda, EnlaceTienda, Producto
from scraper.scrapers import scrape_search_all
from services.categories import match_categories
from services.favorite_notifier import notify_matching_favorites
from services.matching import group_by_family
from services.persistence import LinkUpdate, persist_family
from services.predictor import (
    classify_best_moment,
    compute_discount_percent,
    decimal_to_money,
    load_product_price_history,
    recent_link_prices,
)


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


def _normalize_keyword(keyword: str) -> str:
    return keyword.strip().lower()


def _cheapest_update(updates: list[LinkUpdate]) -> LinkUpdate:
    return min(updates, key=lambda update: update.current_price)


def _store_offers(entries: list[tuple[str, Decimal, str, str | None]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {"store": store, "price": decimal_to_money(price), "url": url, "image_url": image_url}
            for store, price, url, image_url in entries
        ),
        key=lambda store: Decimal(store["price"]),
    )


async def _family_payload(
    session: AsyncSession,
    producto: Producto,
    entries: list[tuple[str, Decimal, str, str | None]],
    discount_percent: Decimal,
) -> dict[str, Any]:
    history = await load_product_price_history(session, producto.id)
    best_moment = classify_best_moment(history)
    historic_min = best_moment.get("historic_min")

    stores = _store_offers(entries)
    cheapest_price = min(price for _, price, _, _ in entries)
    # A product seen for the first time has a single price point, so its
    # historic_min equals its current price and this reads as historic-low
    # trivially - same behavior classify_best_moment already has today.
    is_historic_low = historic_min is not None and cheapest_price <= Decimal(historic_min)
    image_url = next((store["image_url"] for store in stores if store["image_url"]), None)

    return {
        "product_id": producto.id,
        "name": producto.nombre,
        "is_historic_low": is_historic_low,
        "best_status": best_moment.get("status"),
        "discount_percent": str(discount_percent),
        "categories": match_categories(producto.nombre),
        "image_url": image_url,
        "stores": stores,
    }


async def _was_searched_today(session: AsyncSession, keyword_norm: str) -> bool:
    result = await session.execute(select(Busqueda).where(Busqueda.keyword == keyword_norm))
    busqueda = result.scalar_one_or_none()
    if busqueda is None:
        return False
    return busqueda.ultima_busqueda.date() == datetime.utcnow().date()


async def _touch_busqueda(session: AsyncSession, keyword_norm: str) -> None:
    result = await session.execute(select(Busqueda).where(Busqueda.keyword == keyword_norm))
    busqueda = result.scalar_one_or_none()
    now = datetime.utcnow()

    if busqueda is None:
        session.add(Busqueda(keyword=keyword_norm, ultima_busqueda=now))
    else:
        busqueda.ultima_busqueda = now


async def _rebuild_from_db(session: AsyncSession, keyword: str) -> list[dict[str, Any]]:
    # Already scraped this exact keyword today (see _was_searched_today) - the
    # stores themselves won't have moved since then, so this rebuilds the same
    # response straight from Postgres instead of spending another 30-40s
    # hitting 4 live sites for data we already have.
    pattern = f"%{keyword.strip()}%"
    result = await session.execute(select(Producto).where(Producto.nombre.ilike(pattern)))
    productos = result.scalars().all()

    payloads: list[dict[str, Any]] = []

    for producto in productos:
        result = await session.execute(select(EnlaceTienda).where(EnlaceTienda.producto_id == producto.id))
        enlaces = [enlace for enlace in result.scalars().all() if enlace.precio_actual is not None and enlace.url]
        if not enlaces:
            continue

        entries = [(enlace.tienda or "unknown", enlace.precio_actual, enlace.url, enlace.imagen_url) for enlace in enlaces]
        cheapest = min(enlaces, key=lambda enlace: enlace.precio_actual)
        recent = await recent_link_prices(session, cheapest.id)
        discount_percent = compute_discount_percent(recent[1], recent[0]) if len(recent) >= 2 else Decimal("0.00")

        payloads.append(await _family_payload(session, producto, entries, discount_percent))

    return payloads


async def search_products(session: AsyncSession, keyword: str) -> dict[str, Any]:
    redis_client = _get_redis()
    cache_key = _cache_key(keyword)
    keyword_norm = _normalize_keyword(keyword)

    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception as exc:
        # Redis being unavailable must never break search, only skip the cache.
        logger.warning("Search cache read failed for keyword=%r: %s", keyword, exc)

    if await _was_searched_today(session, keyword_norm):
        payloads = await _rebuild_from_db(session, keyword)
    else:
        raw_items = await scrape_search_all(keyword)
        families = group_by_family(raw_items)
        payloads = []

        for family_items in families:
            canonical_name = max(
                (item["name"] for item in family_items if item.get("name")),
                key=len,
                default=keyword,
            )
            producto, updates = await persist_family(session, family_items, canonical_name)

            if not updates:
                continue

            cheapest = _cheapest_update(updates)
            discount_percent = compute_discount_percent(cheapest.previous_price, cheapest.current_price)

            # A price drop detected live (as opposed to via the scheduled
            # 12h refresh in services/tasks.py) should still reach anyone who
            # favorited this product/category - same notify path, just
            # triggered from a different place a drop can be discovered.
            if cheapest.previous_price is not None and cheapest.current_price < cheapest.previous_price:
                await notify_matching_favorites(
                    session, producto, cheapest.previous_price, cheapest.current_price, cheapest.enlace.url
                )

            entries = [
                (update.enlace.tienda or "unknown", update.current_price, update.enlace.url, update.enlace.imagen_url)
                for update in updates
            ]
            payloads.append(await _family_payload(session, producto, entries, discount_percent))

        await _touch_busqueda(session, keyword_norm)
        await session.commit()

    payloads.sort(key=lambda family: (not family["is_historic_low"], -Decimal(family["discount_percent"])))

    response = {"query": keyword, "families": payloads}

    try:
        await redis_client.set(cache_key, json.dumps(response), ex=SEARCH_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Search cache write failed for keyword=%r: %s", keyword, exc)

    return response
