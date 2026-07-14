"""Widen productos.nombre from VARCHAR(255) to unbounded TEXT

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14
"""

import sqlalchemy as sa

from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "productos",
        "nombre",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "productos",
        "nombre",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
