"""Baseline: productos, enlaces_tiendas, historial_precios

Revision ID: 0001
Revises:
Create Date: 2026-07-14
"""

import sqlalchemy as sa

from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ean", sa.String(length=13), nullable=True),
        sa.UniqueConstraint("ean", name="uq_productos_ean"),
    )

    op.create_table(
        "enlaces_tiendas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "producto_id",
            sa.Integer(),
            sa.ForeignKey("productos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tienda", sa.String(length=100), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("precio_actual", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )

    op.create_table(
        "historial_precios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "enlace_id",
            sa.Integer(),
            sa.ForeignKey("enlaces_tiendas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("precio", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("historial_precios")
    op.drop_table("enlaces_tiendas")
    op.drop_table("productos")
