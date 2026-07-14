"""Add imagen_url column to enlaces_tiendas

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14
"""

import sqlalchemy as sa

from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("enlaces_tiendas", sa.Column("imagen_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("enlaces_tiendas", "imagen_url")
