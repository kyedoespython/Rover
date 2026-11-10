"""Add user-owned API key hashes.

Revision ID: 4ac81f0e2d73
Revises: 93f2c0e1a7b4
Create Date: 2026-11-09 21:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "4ac81f0e2d73"
down_revision = "93f2c0e1a7b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_api_keys",
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_name", sa.String(length=128), nullable=False),
        sa.Column("key_type", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["accounts.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("api_key_id"),
        sa.UniqueConstraint("user_id", "key_name", name="uq_user_api_keys_user_name"),
    )
    op.create_index(
        "ix_user_api_keys_user_created",
        "user_api_keys",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_user_api_keys_user_created", table_name="user_api_keys")
    op.drop_table("user_api_keys")
