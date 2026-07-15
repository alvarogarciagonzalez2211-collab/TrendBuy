import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://trendbuy:trendbuy@localhost:5432/trendbuy",
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Text, not String(255): real scraped titles (Amazon especially) routinely
    # exceed 255 chars with full marketing copy and blew up every insert for
    # those products (StringDataRightTruncationError), silently 500-ing the
    # whole search - confirmed live against a real "xiaomi" search.
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    ean: Mapped[str | None] = mapped_column(String(13), unique=True, nullable=True)

    enlaces: Mapped[list["EnlaceTienda"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )
    favoritos: Mapped[list["Favorito"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
    )


class EnlaceTienda(Base):
    __tablename__ = "enlaces_tiendas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"))
    tienda: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    precio_actual: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    producto: Mapped[Producto] = relationship(back_populates="enlaces")
    historial: Mapped[list["HistorialPrecio"]] = relationship(
        back_populates="enlace",
        cascade="all, delete-orphan",
    )


class HistorialPrecio(Base):
    __tablename__ = "historial_precios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enlace_id: Mapped[int] = mapped_column(ForeignKey("enlaces_tiendas.id", ondelete="CASCADE"))
    precio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    enlace: Mapped[EnlaceTienda] = relationship(back_populates="historial")


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    push_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Busqueda(Base):
    __tablename__ = "busquedas"

    # Centralized record of every keyword search ever run against the 4-store
    # scraper - lets services/search.py know "already scraped this today,
    # don't hit the stores again" from a durable source (Postgres) instead of
    # only relying on the Redis cache, and lets the daily Celery beat job
    # (services/tasks.py::refresh_search_keywords) know which keywords to
    # keep refreshing automatically so their price history keeps growing
    # without anyone re-searching by hand.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    ultima_busqueda: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # One-click unsubscribe (see services/auth.py's HMAC token) flips this to
    # False - services/favorite_notifier.py checks it before sending any
    # deal-alert email, independent of the favoritos themselves (a user can
    # opt out of email entirely without losing their favorites/thresholds).
    notificaciones_activas: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    favoritos: Mapped[list["Favorito"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")


class TokenAcceso(Base):
    __tablename__ = "tokens_acceso"

    # One-time magic-link token: random (secrets.token_urlsafe), short-lived,
    # single-use (usado flips true on the FIRST successful confirm - a replay
    # of the same link, e.g. an email-scanner prefetch, must not grant a
    # session). See services/auth.py for issuance/consumption.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Sesion(Base):
    __tablename__ = "sesiones"

    # The session cookie value IS this token - DB-backed (not a signed JWT)
    # so logout / expiry is an immediate, revocable DB row, consistent with
    # the rest of this project treating Postgres as the source of truth.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Categoria(Base):
    __tablename__ = "categorias"

    # Taxonomy itself lives in code (services/categories.py::CATEGORY_KEYWORDS)
    # next to the keyword lists that assign products to it, same pattern as
    # matching.py's whitelists - this table only exists to give favoritos a
    # stable FK target, seeded from that same list at migration time.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Favorito(Base):
    __tablename__ = "favoritos"
    __table_args__ = (
        CheckConstraint(
            "(producto_id IS NOT NULL AND categoria_id IS NULL) "
            "OR (producto_id IS NULL AND categoria_id IS NOT NULL)",
            name="ck_favoritos_producto_xor_categoria",
        ),
        UniqueConstraint("usuario_id", "producto_id", name="uq_favoritos_usuario_producto"),
        UniqueConstraint("usuario_id", "categoria_id", name="uq_favoritos_usuario_categoria"),
    )

    # Exactly one of producto_id/categoria_id is set per row (enforced above):
    # a favorite is either one specific product, or an entire category/theme
    # ("Televisores") - services/tasks.py checks both when a price drops.
    # precio_maximo/descuento_minimo_percent are both optional filters the
    # user sets so they don't get notified about every single drop.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), nullable=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id", ondelete="CASCADE"), nullable=True)
    precio_maximo: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    descuento_minimo_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Skips re-notifying the same favorite for the same day's drop on every
    # 12h scrape cycle - same daily-dedup idea as services/search.py's Busqueda.
    ultima_notificacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    usuario: Mapped[Usuario] = relationship(back_populates="favoritos")
    producto: Mapped[Producto | None] = relationship(back_populates="favoritos")
    categoria: Mapped[Categoria | None] = relationship()


def _run_alembic_upgrade() -> None:
    # Imported lazily so a missing/misconfigured alembic install doesn't break
    # every import of this module, only actual startup.
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    await asyncio.to_thread(_run_alembic_upgrade)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
