from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from models.database import Categoria, Favorito, Usuario, get_session
from services.predictor import decimal_to_money


router = APIRouter(prefix="/api/v1", tags=["favorites"])


def _serialize_favorite(favorito: Favorito) -> dict[str, Any]:
    return {
        "id": favorito.id,
        "producto_id": favorito.producto_id,
        "producto_nombre": favorito.producto.nombre if favorito.producto else None,
        "categoria_id": favorito.categoria_id,
        "categoria_nombre": favorito.categoria.nombre if favorito.categoria else None,
        "precio_maximo": decimal_to_money(favorito.precio_maximo) if favorito.precio_maximo is not None else None,
        "descuento_minimo_percent": (
            str(favorito.descuento_minimo_percent) if favorito.descuento_minimo_percent is not None else None
        ),
    }


@router.get("/categories")
async def list_categories(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    result = await session.execute(select(Categoria).order_by(Categoria.nombre))
    categorias = result.scalars().all()
    return {"categories": [{"id": categoria.id, "nombre": categoria.nombre} for categoria in categorias]}


@router.get("/favorites")
async def list_favorites(
    usuario: Usuario = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    query = (
        select(Favorito)
        .where(Favorito.usuario_id == usuario.id)
        .options(selectinload(Favorito.producto), selectinload(Favorito.categoria))
        .order_by(Favorito.creado_en.desc())
    )
    favoritos = (await session.execute(query)).scalars().all()
    return {"favorites": [_serialize_favorite(favorito) for favorito in favoritos]}


class FavoriteCreate(BaseModel):
    producto_id: int | None = None
    categoria_id: int | None = None
    precio_maximo: Decimal | None = None
    descuento_minimo_percent: Decimal | None = None


@router.post("/favorites", status_code=201)
async def create_favorite(
    payload: FavoriteCreate,
    usuario: Usuario = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if (payload.producto_id is None) == (payload.categoria_id is None):
        raise HTTPException(status_code=400, detail="Indica producto_id o categoria_id, pero no ambos.")

    query = select(Favorito).where(Favorito.usuario_id == usuario.id)
    query = query.where(
        Favorito.producto_id == payload.producto_id
        if payload.producto_id is not None
        else Favorito.categoria_id == payload.categoria_id
    )
    favorito = (await session.execute(query)).scalar_one_or_none()

    # Re-posting an existing product/category favorite just updates its
    # thresholds instead of erroring on the unique constraint - reads as
    # "edit" from the frontend's point of view without a separate PATCH route.
    if favorito is None:
        favorito = Favorito(
            usuario_id=usuario.id,
            producto_id=payload.producto_id,
            categoria_id=payload.categoria_id,
        )
        session.add(favorito)

    favorito.precio_maximo = payload.precio_maximo
    favorito.descuento_minimo_percent = payload.descuento_minimo_percent

    await session.commit()
    await session.refresh(favorito, attribute_names=["producto", "categoria"])

    return _serialize_favorite(favorito)


@router.delete("/favorites/{favorite_id}", status_code=204)
async def delete_favorite(
    favorite_id: int,
    usuario: Usuario = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    query = select(Favorito).where(Favorito.id == favorite_id, Favorito.usuario_id == usuario.id)
    favorito = (await session.execute(query)).scalar_one_or_none()

    if favorito is None:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")

    await session.delete(favorito)
    await session.commit()
