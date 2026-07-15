"""Add per-user Telegram linking (chat id + one-time link code)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15
"""

import sqlalchemy as sa

from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("usuarios", sa.Column("telegram_link_code", sa.String(length=16), nullable=True))
    op.add_column("usuarios", sa.Column("telegram_link_code_expira_en", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_usuarios_telegram_chat_id", "usuarios", ["telegram_chat_id"])
    op.create_unique_constraint("uq_usuarios_telegram_link_code", "usuarios", ["telegram_link_code"])


def downgrade() -> None:
    op.drop_constraint("uq_usuarios_telegram_link_code", "usuarios", type_="unique")
    op.drop_constraint("uq_usuarios_telegram_chat_id", "usuarios", type_="unique")
    op.drop_column("usuarios", "telegram_link_code_expira_en")
    op.drop_column("usuarios", "telegram_link_code")
    op.drop_column("usuarios", "telegram_chat_id")
