"""Add notificaciones_activas to usuarios (one-click unsubscribe)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("notificaciones_activas", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "notificaciones_activas")
