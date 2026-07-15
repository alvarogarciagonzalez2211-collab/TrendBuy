import logging
from decimal import Decimal
from typing import Any

from asgiref.sync import async_to_sync
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.database import AsyncSessionLocal, Busqueda, EnlaceTienda, HistorialPrecio
from scraper.scrapers import scrape_store_url, serialize_scraped_product
from services.affiliate import tag_url
from services.celery_app import celery_app
from services.favorite_notifier import notify_matching_favorites
from services.notifier import send_telegram_alert
from services.push_notifier import notify_deal_push
from services.search import search_products


logger = logging.getLogger(__name__)
ALERT_THRESHOLD_PERCENT = Decimal("15.00")


async def notify_deal(product_name: str, old_price: Decimal, new_price: Decimal, url: str) -> bool:
    try:
        sent = await send_telegram_alert(product_name, old_price, new_price, url)
        logger.info("Telegram alert sent=%s product=%s new_price=%s", sent, product_name, new_price)
        return sent
    except Exception as exc:
        logger.exception("Telegram alert failed for product=%s: %s", product_name, exc)
        return False


def calculate_discount_percent(previous_price: Decimal, current_price: Decimal) -> Decimal:
    if previous_price <= 0:
        return Decimal("0.00")

    return ((previous_price - current_price) / previous_price * Decimal("100")).quantize(
        Decimal("0.01")
    )


async def scrape_all_tracked_prices() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    alerts: list[dict[str, str]] = []

    async with AsyncSessionLocal() as session:
        query = select(EnlaceTienda).options(selectinload(EnlaceTienda.producto))
        enlaces = (await session.execute(query)).scalars().all()

        for enlace in enlaces:
            if not enlace.url:
                continue

            previous_price = enlace.precio_actual
            scraped = await scrape_store_url(enlace.tienda or "", enlace.url)
            current_price = scraped.get("price")
            product_name = enlace.producto.nombre if enlace.producto else scraped.get("name")

            if current_price is None:
                logger.warning(
                    "No price scraped for enlace_id=%s store=%s url=%s error=%s",
                    enlace.id,
                    enlace.tienda,
                    enlace.url,
                    scraped.get("error"),
                )
                results.append(serialize_scraped_product(scraped))
                continue

            enlace.precio_actual = current_price
            session.add(HistorialPrecio(enlace_id=enlace.id, precio=current_price))

            if previous_price is not None:
                discount_percent = calculate_discount_percent(previous_price, current_price)
                # Tagged once, reused by every alert channel below - see
                # services/affiliate.py. A no-op passthrough until the real
                # affiliate program env vars are set.
                outbound_url = tag_url(enlace.url, enlace.tienda)

                # Independent of the broadcast threshold below: a favorite's
                # own precio_maximo/descuento_minimo_percent decides whether
                # ITS owner gets emailed, on every real drop - not gated by
                # ALERT_THRESHOLD_PERCENT, which only controls the Telegram/
                # push broadcast that already existed before per-user favorites.
                favorites_notified = 0
                if enlace.producto is not None and current_price < previous_price:
                    favorites_notified = await notify_matching_favorites(
                        session, enlace.producto, previous_price, current_price, outbound_url
                    )

                if discount_percent > ALERT_THRESHOLD_PERCENT:
                    alert_sent = await notify_deal(
                        product_name or "Producto sin nombre",
                        previous_price,
                        current_price,
                        outbound_url,
                    )
                    push_sent = await notify_deal_push(
                        session,
                        product_name or "Producto sin nombre",
                        previous_price,
                        current_price,
                        outbound_url,
                    )
                    alerts.append(
                        {
                            "product": product_name or "Producto sin nombre",
                            "store": enlace.tienda or "unknown",
                            "previous_price": str(previous_price),
                            "current_price": str(current_price),
                            "discount_percent": str(discount_percent),
                            "telegram_sent": str(alert_sent),
                            "push_sent": str(push_sent),
                            "favorites_notified": str(favorites_notified),
                        }
                    )

            results.append(serialize_scraped_product(scraped))

        await session.commit()

    return {
        "tracked_links": len(results),
        "alerts": alerts,
        "results": results,
    }


@celery_app.task(name="services.tasks.scrape_prices")
def scrape_prices() -> dict[str, Any]:
    return async_to_sync(scrape_all_tracked_prices)()


async def refresh_all_search_keywords() -> dict[str, Any]:
    # Complements scrape_prices above: that task refreshes prices for links
    # already tracked, but can't discover a brand-new listing that shows up
    # for a keyword after the last time someone searched it. Re-running every
    # keyword ever searched (services/search.py::search_products, same path
    # a live user search takes) keeps both prices AND the result set fresh
    # without anyone needing to re-type a search - see services/search.py's
    # Busqueda-backed daily dedup, which this task's calls feed into.
    #
    # Runs sequentially, not gathered in parallel: each keyword already opens
    # 4 concurrent store contexts (see scraper.scrapers.scrape_search_all) -
    # fanning many keywords out at once would multiply that further and is
    # more likely to trip bot detection than a few extra minutes of runtime.
    async with AsyncSessionLocal() as session:
        keywords = list((await session.execute(select(Busqueda.keyword))).scalars().all())

    summary: dict[str, Any] = {"keywords": len(keywords), "refreshed": 0, "failed": 0}

    for keyword in keywords:
        async with AsyncSessionLocal() as session:
            try:
                await search_products(session, keyword)
                summary["refreshed"] += 1
            except Exception as exc:
                logger.warning("Keyword refresh failed for keyword=%r: %s", keyword, exc)
                summary["failed"] += 1

    return summary


@celery_app.task(name="services.tasks.refresh_search_keywords")
def refresh_search_keywords() -> dict[str, Any]:
    return async_to_sync(refresh_all_search_keywords)()
