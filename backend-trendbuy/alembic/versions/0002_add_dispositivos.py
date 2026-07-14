"""Add dispositivos table for push notification tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14
"""

import sqlalchemy as sa

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispositivos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("push_token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "creado_en",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("push_token", name="uq_dispositivos_push_token"),
    )


def downgrade() -> None:
    op.drop_table("dispositivos")
