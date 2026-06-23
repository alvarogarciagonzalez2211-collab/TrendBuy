import os
from collections.abc import AsyncGenerator
from datetime import datetime
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
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
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(13), unique=True, nullable=True)

    enlaces: Mapped[list["EnlaceTienda"]] = relationship(
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


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
