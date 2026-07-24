"""Seed categorias missing since the taxonomy outgrew the 0006 seed

0006 seeded the original 8 tech categories; services/categories.py has since
grown Ropa/Hogar/Belleza (session 2026-07-15) and now Deportes/Libros/Juguetes.
Without rows here those categories are tagged on products and filterable, but
can't be favorited "by theme" (api/favorites.py joins on categorias.nombre).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Must match services/categories.py::CATEGORY_KEYWORDS keys - the notifier
# matches favorites by exact nombre string.
NEW_CATEGORY_NAMES = [
    "Ropa",
    "Hogar",
    "Belleza",
    "Deportes",
    "Libros",
    "Juguetes",
]


def upgrade() -> None:
    categorias = sa.table("categorias", sa.column("nombre", sa.String))
    connection = op.get_bind()
    existing = {
        row[0]
        for row in connection.execute(sa.select(categorias.c.nombre)).fetchall()
    }
    missing = [nombre for nombre in NEW_CATEGORY_NAMES if nombre not in existing]
    if missing:
        op.bulk_insert(categorias, [{"nombre": nombre} for nombre in missing])


def downgrade() -> None:
    categorias = sa.table("categorias", sa.column("nombre", sa.String))
    op.execute(
        categorias.delete().where(categorias.c.nombre.in_(NEW_CATEGORY_NAMES))
    )
