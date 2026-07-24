import hashlib
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import router as auth_router
from api.favorites import router as favorites_router
from api.telegram import router as telegram_router
from models.database import Dispositivo, Producto, get_session, init_db
from scraper.scrapers import scrape_comparison
from services.affiliate import tag_url
from services.categories import match_categories
from services.metrics import get_click_stats, record_click
from services.notifier import set_telegram_webhook
from services.persistence import persist_family
from services.predictor import (
    analyze_product,
    classify_best_moment,
    compute_discount_percent,
    decimal_to_money,
    history_sparkline,
    load_product_price_history,
    recent_link_prices,
)
from services.search import is_supported_store_url
from services.search import search_products as run_product_search
from services.search import track_url


logger = logging.getLogger(__name__)


def store_id(store: str | None) -> str:
    value = (store or "unknown").lower().strip()

    if "amazon" in value:
        return "amazon_es"

    if "pccomponentes" in value or "pc componentes" in value:
        return "pccomponentes"

    return value.replace(" ", "_")


def serialize_api_product(product: dict[str, Any]) -> dict[str, Any]:
    price = product.get("price")
    store = product.get("store")
    name = product.get("name") or "Producto sin nombre"
    identity = hashlib.sha1(str(product.get("url", name)).encode("utf-8")).hexdigest()[:12]

    return {
        "id": f"{store_id(store)}-{identity}",
        "storeId": store_id(store),
        "store": store or "unknown",
        "name": name,
        "price": decimal_to_money(price) if price is not None else None,
        "currency": "EUR",
        "url": tag_url(product.get("url"), store),
        "error": product.get("error"),
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await _configure_telegram_webhook()
    yield


async def _configure_telegram_webhook() -> None:
    # Self-configuring on every startup so a restart (or a fresh Cloudflare
    # tunnel URL, which changes on every `cloudflared` run) keeps the webhook
    # pointed at wherever FRONTEND_URL currently says the public site lives -
    # same reasoning as FRONTEND_URL feeding the magic-link email.
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token or not webhook_secret:
        return

    if frontend_url.startswith("http://localhost") or frontend_url.startswith("http://127.0.0.1"):
        logger.warning("Telegram webhook not configured: FRONTEND_URL is localhost, Telegram requires public HTTPS.")
        return

    webhook_url = f"{frontend_url}/backend/api/v1/telegram/webhook"
    try:
        await set_telegram_webhook(webhook_url, webhook_secret)
    except Exception:
        logger.exception("Failed to configure Telegram webhook at startup.")


app = FastAPI(title="TrendBuy API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(favorites_router)
app.include_router(telegram_router)


async def persist_scraped_products(
    session: AsyncSession,
    query: str,
    products: list[dict[str, Any]],
) -> None:
    fallback_name = query.strip() or "Producto sin nombre"
    canonical_name = next((item["name"] for item in products if item.get("name")), fallback_name)
    await persist_family(session, products, canonical_name)
    await session.commit()


@app.get("/api/v1/products/compare")
async def compare_products(
    query: str = Query(..., min_length=1, description="Product name, SKU, EAN or internal search query."),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scraped_products = await scrape_comparison()
    await persist_scraped_products(session, query, scraped_products)
    serialized_products = [serialize_api_product(item) for item in scraped_products]
    valid_products = [item for item in serialized_products if item["price"] is not None]
    errors = [
        {
            "store": item["store"],
            "url": item["url"],
            "error": item["error"] or "Price not available",
        }
        for item in serialized_products
        if item["price"] is None or item["error"]
    ]

    if not valid_products:
        return {
            "error": "No se pudieron obtener precios para esta busqueda.",
            "products": [],
            "meta": {
                "query": query,
                "sourceCount": len(scraped_products),
                "errors": errors,
            },
        }

    return {
        "query": query,
        "products": valid_products,
        "meta": {
            "query": query,
            "sourceCount": len(scraped_products),
            "errors": errors,
        },
    }


@app.get("/api/search")
async def search_products(
    q: str = Query(..., min_length=1, description="Product search query."),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await compare_products(query=q, session=session)


# Only these statuses count as an actual "deal" worth surfacing on the home
# screen; order here doubles as the sort priority (best first).
DASHBOARD_DEAL_STATUSES = ("Óptimo", "Buena Compra")
_DASHBOARD_STATUS_RANK = {status: rank for rank, status in enumerate(DASHBOARD_DEAL_STATUSES)}


@app.get("/api/v1/products/dashboard")
async def get_products_dashboard(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(select(Producto).options(selectinload(Producto.enlaces)))
    products = result.scalars().all()
    dashboard_items = []

    for product in products:
        priced_links = [link for link in product.enlaces if link.precio_actual is not None]
        cheapest_link = min(priced_links, key=lambda link: link.precio_actual) if priced_links else None
        latest_link = (
            max(priced_links, key=lambda link: link.actualizado_en or datetime.min)
            if priced_links
            else None
        )
        history = await load_product_price_history(session, product.id)
        best_moment = classify_best_moment(history)

        if best_moment["status"] not in DASHBOARD_DEAL_STATUSES:
            continue

        # Same zero-tolerance comparison as services/search.py::search_products -
        # deliberately stricter than the 5% band "Óptimo" uses internally.
        # has_price_history (>= 2 distinct tracked days) keeps a just-added
        # product from trivially claiming its only price as a historic low.
        historic_min = best_moment.get("historic_min")
        is_historic_low = (
            cheapest_link is not None
            and historic_min is not None
            and cheapest_link.precio_actual <= Decimal(historic_min)
            and bool(best_moment.get("has_price_history"))
        )
        image_url = next(
            (link.imagen_url for link in (cheapest_link, latest_link) if link and link.imagen_url),
            None,
        )

        # Same idea as services/search.py::_family_payload's discount_percent -
        # compares the cheapest link's last two recorded prices, not an estimate.
        discount_percent = Decimal("0.00")
        if cheapest_link is not None:
            recent_prices = await recent_link_prices(session, cheapest_link.id)
            if len(recent_prices) >= 2:
                discount_percent = compute_discount_percent(recent_prices[1], recent_prices[0])

        dashboard_items.append(
            {
                "product_id": product.id,
                "name": product.nombre,
                "ean": product.ean,
                "last_price": decimal_to_money(latest_link.precio_actual) if latest_link else None,
                "last_store": latest_link.tienda if latest_link else None,
                "cheapest_price": decimal_to_money(cheapest_link.precio_actual) if cheapest_link else None,
                "cheapest_store": cheapest_link.tienda if cheapest_link else None,
                "cheapest_url": tag_url(cheapest_link.url, cheapest_link.tienda) if cheapest_link else None,
                "currency": "EUR",
                "status": best_moment["status"],
                "is_historic_low": is_historic_low,
                "discount_percent": str(discount_percent),
                "categories": match_categories(product.nombre),
                "image_url": image_url,
                "days_tracked": best_moment.get("days_tracked", 0),
                "history_spark": history_sparkline(history),
                "tracked_links": len(product.enlaces),
            }
        )

    # Best status first, cheapest price first within the same status - the
    # frontend renders this order as-is rather than re-ranking client-side.
    dashboard_items.sort(
        key=lambda item: (
            _DASHBOARD_STATUS_RANK[item["status"]],
            Decimal(item["cheapest_price"]) if item["cheapest_price"] is not None else Decimal("Infinity"),
        )
    )

    return {"products": dashboard_items}


@app.get("/api/v1/products/{product_id}/analysis")
async def get_product_analysis(
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    analysis = await analyze_product(session, product_id)

    if analysis is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return analysis


@app.get("/api/v1/search")
async def search_endpoint(
    q: str = Query(..., min_length=1, description="Keyword search across every supported store."),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await run_product_search(session, q)


class TrackUrlRequest(BaseModel):
    url: str


@app.post("/api/v1/track")
async def track_by_url(
    payload: TrackUrlRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    url = payload.url.strip()

    if not url or not is_supported_store_url(url):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ese enlace no es de una tienda soportada. Tiendas disponibles: "
                "Amazon.es, PcComponentes, MediaMarkt, Worten, IKEA, Vinted, Druni, "
                "Decathlon, Sprinter, Primor y Casa del Libro."
            ),
        )

    family = await track_url(session, url)
    if family is None:
        raise HTTPException(
            status_code=422,
            detail="No se pudo leer el precio de ese enlace. Comprueba que sea la pagina de un producto concreto.",
        )

    return family


class ClickEvent(BaseModel):
    store: str
    source: Literal["dashboard", "search", "alert", "web"] = "web"


@app.post("/api/v1/metrics/click", status_code=204)
async def record_outbound_click(payload: ClickEvent) -> None:
    # Beacon fired by the frontend right as a user clicks out to a store -
    # backs monetization decisions (see services/metrics.py). Always 204:
    # a metrics hiccup must never surface to the user mid-purchase.
    store = payload.store.strip()
    if store:
        await record_click(store, payload.source)


@app.get("/api/v1/metrics/clicks")
async def get_outbound_click_stats(
    days: int = Query(30, ge=1, le=90),
    x_admin_key: str = Header(""),
) -> dict[str, Any]:
    # Same SECRET_KEY that already signs unsubscribe links - it's the one
    # secret guaranteed to be set in any real deployment, and this endpoint
    # is for the operator, not end users.
    secret = os.getenv("SECRET_KEY", "")
    if not secret or not secrets.compare_digest(x_admin_key, secret):
        raise HTTPException(status_code=403, detail="Invalid admin key")

    return await get_click_stats(days)


class DeviceRegistration(BaseModel):
    push_token: str
    platform: Literal["ios", "android"]


@app.post("/api/v1/devices", status_code=201)
async def register_device(
    payload: DeviceRegistration,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(select(Dispositivo).where(Dispositivo.push_token == payload.push_token))
    device = result.scalar_one_or_none()

    if device is None:
        device = Dispositivo(push_token=payload.push_token, platform=payload.platform)
        session.add(device)
    else:
        device.platform = payload.platform
        device.activo = True

    await session.commit()

    return {
        "id": device.id,
        "push_token": device.push_token,
        "platform": device.platform,
        "activo": device.activo,
    }
