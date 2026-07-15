import asyncio
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd
from prophet import Prophet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import EnlaceTienda, HistorialPrecio, Producto


MIN_FORECAST_POINTS = 3

# A product scraped for the first time has exactly one price point, so its
# current price IS its historic minimum trivially - every fresh search used to
# light up the "mínimo histórico" badge on all results. Requiring price records
# on at least this many DISTINCT days keeps the badge meaningful: it can only
# appear once there is a real history to be the minimum OF.
MIN_HISTORY_DAYS_FOR_LOW = 2


def decimal_to_money(value: float | int | Decimal | None) -> str | None:
    if value is None:
        return None

    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_discount_percent(previous_price: Decimal | None, current_price: Decimal) -> Decimal:
    if previous_price is None or previous_price <= 0:
        return Decimal("0.00")

    return ((previous_price - current_price) / previous_price * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


async def recent_link_prices(session: AsyncSession, enlace_id: int, limit: int = 2) -> list[Decimal]:
    query = (
        select(HistorialPrecio.precio)
        .where(HistorialPrecio.enlace_id == enlace_id)
        .where(HistorialPrecio.precio.is_not(None))
        .order_by(HistorialPrecio.fecha.desc())
        .limit(limit)
    )
    return list((await session.execute(query)).scalars().all())


async def load_product_price_history(session: AsyncSession, product_id: int) -> pd.DataFrame:
    query = (
        select(
            Producto.id.label("product_id"),
            Producto.nombre.label("product_name"),
            EnlaceTienda.id.label("link_id"),
            EnlaceTienda.tienda.label("store"),
            HistorialPrecio.fecha.label("fecha"),
            HistorialPrecio.precio.label("precio"),
        )
        .join(EnlaceTienda, EnlaceTienda.producto_id == Producto.id)
        .join(HistorialPrecio, HistorialPrecio.enlace_id == EnlaceTienda.id)
        .where(Producto.id == product_id)
        .where(HistorialPrecio.precio.is_not(None))
        .order_by(HistorialPrecio.fecha.asc())
    )
    rows = (await session.execute(query)).mappings().all()

    return pd.DataFrame(rows)


async def get_product_name(session: AsyncSession, product_id: int) -> str | None:
    result = await session.execute(select(Producto.nombre).where(Producto.id == product_id))
    return result.scalar_one_or_none()


async def get_product_image(session: AsyncSession, product_id: int) -> str | None:
    query = (
        select(EnlaceTienda.imagen_url)
        .where(EnlaceTienda.producto_id == product_id)
        .where(EnlaceTienda.imagen_url.is_not(None))
        .order_by(EnlaceTienda.actualizado_en.desc())
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


def classify_best_moment(history: pd.DataFrame) -> dict[str, Any]:
    if history.empty:
        return {
            "status": "Sin datos",
            "current_price": None,
            "percentile_25": None,
            "historic_min": None,
            "message": "No hay historial de precios para analizar.",
        }

    prices = pd.to_numeric(history["precio"], errors="coerce").dropna()
    if prices.empty:
        return {
            "status": "Sin datos",
            "current_price": None,
            "percentile_25": None,
            "historic_min": None,
            "message": "El historial no contiene precios validos.",
        }

    # Days (not raw records) with at least one valid price - a single scrape
    # of N stores writes N records but still only proves one day of history.
    distinct_days = int(pd.to_datetime(history.loc[prices.index, "fecha"]).dt.normalize().nunique())

    current_price = Decimal(str(prices.iloc[-1]))
    percentile_25 = Decimal(str(prices.quantile(0.25)))
    historic_min = Decimal(str(prices.min()))
    near_min_limit = historic_min * Decimal("1.05")

    if current_price <= near_min_limit:
        status = "\u00d3ptimo"
    elif current_price <= percentile_25:
        status = "Buena Compra"
    else:
        status = "Esperar"

    return {
        "status": status,
        "current_price": decimal_to_money(current_price),
        "percentile_25": decimal_to_money(percentile_25),
        "historic_min": decimal_to_money(historic_min),
        "records": int(len(prices)),
        "days_tracked": distinct_days,
        # Callers deciding whether to show a historic-low badge must AND this
        # in - see MIN_HISTORY_DAYS_FOR_LOW above for why one day never counts.
        "has_price_history": distinct_days >= MIN_HISTORY_DAYS_FOR_LOW,
    }


def history_sparkline(history: pd.DataFrame, points: int = 30) -> list[float]:
    # Tiny inline trend for product cards: one value per tracked day (the
    # day's cheapest price across stores), most recent `points` days. Floats,
    # not money strings - this feeds an SVG polyline, never a price label, so
    # Decimal-grade precision buys nothing here.
    if history.empty:
        return []

    frame = history[["fecha", "precio"]].copy()
    frame["precio"] = pd.to_numeric(frame["precio"], errors="coerce")
    frame = frame.dropna(subset=["precio"])
    if frame.empty:
        return []

    daily_min = frame.groupby(pd.to_datetime(frame["fecha"]).dt.normalize())["precio"].min().sort_index()
    return [float(value) for value in daily_min.tail(points)]


def build_prophet_frame(history: pd.DataFrame) -> pd.DataFrame:
    forecast_frame = history[["fecha", "precio"]].copy()
    forecast_frame["fecha"] = pd.to_datetime(forecast_frame["fecha"], utc=False)
    forecast_frame["precio"] = pd.to_numeric(forecast_frame["precio"], errors="coerce")
    forecast_frame = forecast_frame.dropna(subset=["fecha", "precio"])
    forecast_frame = forecast_frame.rename(columns={"fecha": "ds", "precio": "y"})

    return forecast_frame.groupby("ds", as_index=False)["y"].mean().sort_values("ds")


def train_and_forecast(history: pd.DataFrame, days: int = 30) -> list[dict[str, str]]:
    prophet_frame = build_prophet_frame(history)
    if len(prophet_frame) < MIN_FORECAST_POINTS:
        return []

    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False)
    model.fit(prophet_frame)

    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future).tail(days)

    return [
        {
            "ds": row.ds.date().isoformat(),
            "yhat": decimal_to_money(row.yhat),
            "yhat_lower": decimal_to_money(row.yhat_lower),
            "yhat_upper": decimal_to_money(row.yhat_upper),
        }
        for row in forecast.itertuples(index=False)
    ]


def serialize_history(history: pd.DataFrame) -> list[dict[str, str | int | None]]:
    if history.empty:
        return []

    ordered = history.sort_values("fecha")
    return [
        {
            "link_id": int(row.link_id),
            "store": row.store,
            "date": row.fecha.isoformat() if row.fecha is not None else None,
            "price": decimal_to_money(row.precio),
        }
        for row in ordered.itertuples(index=False)
    ]


async def analyze_product(session: AsyncSession, product_id: int) -> dict[str, Any] | None:
    product_name = await get_product_name(session, product_id)
    if product_name is None:
        return None

    history = await load_product_price_history(session, product_id)
    best_moment = classify_best_moment(history)
    image_url = await get_product_image(session, product_id)
    warnings = []

    if len(history) < MIN_FORECAST_POINTS:
        warnings.append(
            f"Se necesitan al menos {MIN_FORECAST_POINTS} registros de precio para generar prediccion."
        )
        forecast: list[dict[str, str]] = []
    else:
        try:
            forecast = await asyncio.to_thread(train_and_forecast, history, 30)
        except Exception as exc:
            warnings.append(f"No se pudo generar la prediccion: {type(exc).__name__}: {exc}")
            forecast = []

    return {
        "product_id": product_id,
        "product_name": product_name,
        "image_url": image_url,
        "best_moment": best_moment,
        "history": serialize_history(history),
        "forecast_30_days": forecast,
        "warnings": warnings,
    }
