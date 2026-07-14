import logging
from decimal import Decimal
from typing import Any

from asgiref.sync import async_to_sync
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.database import AsyncSessionLocal, EnlaceTienda, HistorialPrecio
from scraper.scrapers import scrape_store_url, serialize_scraped_product
from services.celery_app import celery_app
from services.notifier import send_telegram_alert
from services.push_notifier import notify_deal_push


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
                if discount_percent > ALERT_THRESHOLD_PERCENT:
                    alert_sent = await notify_deal(
                        product_name or "Producto sin nombre",
                        previous_price,
                        current_price,
                        enlace.url,
                    )
                    push_sent = await notify_deal_push(
                        session,
                        product_name or "Producto sin nombre",
                        previous_price,
                        current_price,
                        enlace.url,
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
