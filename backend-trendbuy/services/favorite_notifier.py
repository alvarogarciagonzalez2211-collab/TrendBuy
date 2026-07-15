import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.database import Categoria, Favorito, Producto
from services.categories import match_categories
from services.email_sender import send_deal_alert_email


logger = logging.getLogger(__name__)


async def notify_matching_favorites(
    session: AsyncSession,
    producto: Producto,
    previous_price: Decimal,
    current_price: Decimal,
    url: str,
) -> int:
    # Separate from the broadcast Telegram/push alert in tasks.py, which only
    # fires above the fixed 15% ALERT_THRESHOLD_PERCENT - a favorite's own
    # precio_maximo/descuento_minimo_percent is independent of that global
    # threshold, so this runs on every real drop, not just the big ones.
    if current_price >= previous_price:
        return 0

    discount_percent = ((previous_price - current_price) / previous_price * Decimal("100")).quantize(Decimal("0.01"))

    category_names = match_categories(producto.nombre)
    category_ids: list[int] = []
    if category_names:
        result = await session.execute(select(Categoria.id).where(Categoria.nombre.in_(category_names)))
        category_ids = list(result.scalars().all())

    conditions = [Favorito.producto_id == producto.id]
    if category_ids:
        conditions.append(Favorito.categoria_id.in_(category_ids))

    query = select(Favorito).where(or_(*conditions)).options(selectinload(Favorito.usuario))
    favoritos = (await session.execute(query)).scalars().all()

    today = datetime.utcnow().date()
    sent = 0

    for favorito in favoritos:
        # Same daily-dedup idea as services/search.py's Busqueda: a product
        # tracked every 12h shouldn't email the same user twice for the
        # price staying low the whole day.
        if favorito.ultima_notificacion is not None and favorito.ultima_notificacion.date() == today:
            continue

        if favorito.precio_maximo is not None and current_price > favorito.precio_maximo:
            continue

        if favorito.descuento_minimo_percent is not None and discount_percent < favorito.descuento_minimo_percent:
            continue

        try:
            ok = await send_deal_alert_email(
                favorito.usuario.email, producto.nombre, previous_price, current_price, url
            )
        except Exception as exc:
            logger.exception("Favorite alert email failed for favorito_id=%s: %s", favorito.id, exc)
            continue

        if ok:
            favorito.ultima_notificacion = datetime.utcnow()
            sent += 1

    return sent
