"""Add usuarios, tokens_acceso, sesiones, categorias, favoritos

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Kept in sync by hand with services/categories.py::CATEGORY_KEYWORDS - only
# the names need to exist here, the keyword lists themselves live in code.
CATEGORY_NAMES = [
    "Moviles",
    "Televisores",
    "Portatiles",
    "Tablets",
    "Auriculares",
    "Videojuegos",
    "Electrodomesticos",
    "Informatica",
]


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("creado_en", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("ultimo_login", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )

    op.create_table(
        "tokens_acceso",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("creado_en", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("token", name="uq_tokens_acceso_token"),
    )

    op.create_table(
        "sesiones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("token", name="uq_sesiones_token"),
    )

    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_categorias_nombre"),
    )

    categorias_table = sa.table("categorias", sa.column("nombre", sa.String))
    op.bulk_insert(categorias_table, [{"nombre": nombre} for nombre in CATEGORY_NAMES])

    op.create_table(
        "favoritos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=True),
        sa.Column("categoria_id", sa.Integer(), sa.ForeignKey("categorias.id", ondelete="CASCADE"), nullable=True),
        sa.Column("precio_maximo", sa.Numeric(10, 2), nullable=True),
        sa.Column("descuento_minimo_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("ultima_notificacion", sa.DateTime(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(
            "(producto_id IS NOT NULL AND categoria_id IS NULL) "
            "OR (producto_id IS NULL AND categoria_id IS NOT NULL)",
            name="ck_favoritos_producto_xor_categoria",
        ),
        sa.UniqueConstraint("usuario_id", "producto_id", name="uq_favoritos_usuario_producto"),
        sa.UniqueConstraint("usuario_id", "categoria_id", name="uq_favoritos_usuario_categoria"),
    )


def downgrade() -> None:
    op.drop_table("favoritos")
    op.drop_table("categorias")
    op.drop_table("sesiones")
    op.drop_table("tokens_acceso")
    op.drop_table("usuarios")
