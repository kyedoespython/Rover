"""Leave the AI provider unselected for new accounts.

Revision ID: e12a73b4c905
Revises: d8a4c391e206
"""
from alembic import op
import sqlalchemy as sa

revision = "e12a73b4c905"
down_revision = "d8a4c391e206"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column(
            "rover_ai_provider",
            existing_type=sa.String(16),
            existing_nullable=False,
            server_default="unselected",
        )


def downgrade():
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column(
            "rover_ai_provider",
            existing_type=sa.String(16),
            existing_nullable=False,
            server_default="ollama",
        )
