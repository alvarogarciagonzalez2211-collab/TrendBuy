from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import EnlaceTienda, HistorialPrecio, Producto
from services.matching import DEFAULT_THRESHOLD, find_matching_producto


async def get_or_create_enlace(
    session: AsyncSession,
    producto_id: int,
    tienda: str,
    url: str,
) -> EnlaceTienda:
    result = await session.execute(
        select(EnlaceTienda).where(
            EnlaceTienda.producto_id == producto_id,
            EnlaceTienda.tienda == tienda,
            EnlaceTienda.url == url,
        )
    )
    enlace = result.scalar_one_or_none()

    if enlace is not None:
        return enlace

    enlace = EnlaceTienda(producto_id=producto_id, tienda=tienda, url=url)
    session.add(enlace)
    await session.flush()
    return enlace


@dataclass
class LinkUpdate:
    enlace: EnlaceTienda
    previous_price: Decimal | None
    current_price: Decimal


async def persist_family(
    session: AsyncSession,
    family_items: list[dict[str, Any]],
    canonical_name_hint: str,
    fuzzy_threshold: float = DEFAULT_THRESHOLD,
) -> tuple[Producto, list[LinkUpdate]]:
    producto = await find_matching_producto(session, canonical_name_hint, fuzzy_threshold)

    if producto is None:
        producto = Producto(nombre=canonical_name_hint)
        session.add(producto)
        await session.flush()

    updates: list[LinkUpdate] = []

    for item in family_items:
        price = item.get("price")
        if price is None or not item.get("url"):
            continue

        enlace = await get_or_create_enlace(session, producto.id, item["store"], item["url"])
        previous_price = enlace.precio_actual
        enlace.precio_actual = price
        # Keep the last known good image on a transient scrape miss instead of
        # blanking it out - only overwrite when this pass actually found one.
        if item.get("image_url"):
            enlace.imagen_url = item["image_url"]
        session.add(HistorialPrecio(enlace_id=enlace.id, precio=price))
        updates.append(LinkUpdate(enlace=enlace, previous_price=previous_price, current_price=price))

    return producto, updates
