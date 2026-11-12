"""Add Gemini preferences for Rover AI.

Revision ID: d8a4c391e206
Revises: af41c8e20d73
"""
from alembic import op
import sqlalchemy as sa

revision = "d8a4c391e206"
down_revision = "af41c8e20d73"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column("rover_ai_provider", sa.String(16), server_default="ollama", nullable=False),
    )
    op.add_column("accounts", sa.Column("gemini_model", sa.String(128), nullable=True))
    op.add_column("accounts", sa.Column("active_gemini_api_key_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("accounts", "active_gemini_api_key_id")
    op.drop_column("accounts", "gemini_model")
    op.drop_column("accounts", "rover_ai_provider")
