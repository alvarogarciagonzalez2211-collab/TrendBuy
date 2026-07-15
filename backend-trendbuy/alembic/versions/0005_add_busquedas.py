"""Add busquedas table for daily keyword-search dedup and auto-refresh

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14
"""

import sqlalchemy as sa

from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "busquedas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("ultima_busqueda", sa.DateTime(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("keyword", name="uq_busquedas_keyword"),
    )


def downgrade() -> None:
    op.drop_table("busquedas")
