"""Store Ollama credentials and per-user model preferences.

Revision ID: 8d21a6c45f90
Revises: 4ac81f0e2d73
Create Date: 2026-11-09 22:36:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8d21a6c45f90"
down_revision = "4ac81f0e2d73"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_api_keys",
        sa.Column("key_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("ollama_model", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("active_ollama_api_key_id", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("accounts", "active_ollama_api_key_id")
    op.drop_column("accounts", "ollama_model")
    op.drop_column("user_api_keys", "key_ciphertext")
