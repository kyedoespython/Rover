"""Add encrypted Rover AI attachments.

Revision ID: af41c8e20d73
Revises: c5d8e2a41f90
"""
from alembic import op
import sqlalchemy as sa

revision = "af41c8e20d73"
down_revision = "c5d8e2a41f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chatbot_files",
        sa.Column("file_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.user_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chatbot_files_user_id", "chatbot_files", ["user_id"])


def downgrade():
    op.drop_index("ix_chatbot_files_user_id", table_name="chatbot_files")
    op.drop_table("chatbot_files")
