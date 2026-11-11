"""Add password reset tokens and session versioning.

Revision ID: 7c2d9a41e6b3
Revises: b493a19f6c02
Create Date: 2026-11-11 05:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7c2d9a41e6b3"
down_revision = "b493a19f6c02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("reset_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("reset_id"),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade():
    op.drop_table("password_reset_tokens")
    op.drop_column("accounts", "session_version")
