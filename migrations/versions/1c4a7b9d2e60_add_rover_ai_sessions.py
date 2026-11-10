"""Add Rover AI configuration, permissions, and session history.

Revision ID: 1c4a7b9d2e60
Revises: 8d21a6c45f90
Create Date: 2026-11-10 04:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "1c4a7b9d2e60"
down_revision = "8d21a6c45f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chatbots",
        sa.Column("chatbot_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "chatbot_name",
            sa.String(length=64),
            server_default="Rover AI",
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["accounts.user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chatbot_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "chatbot_metadata",
        sa.Column("chatbot_id", sa.Integer(), nullable=False),
        sa.Column(
            "allow_folder_read",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "allow_folder_write",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chatbot_id"],
            ["chatbots.chatbot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chatbot_id"),
    )
    op.create_table(
        "chatbot_sessions",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("chatbot_id", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chatbot_id"],
            ["chatbots.chatbot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_chatbot_sessions_chatbot_started",
        "chatbot_sessions",
        ["chatbot_id", "started_at"],
        unique=False,
    )
    op.create_table(
        "chatbot_messages",
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chatbot_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chatbot_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_chatbot_messages_session_id",
        "chatbot_messages",
        ["session_id", "message_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_chatbot_messages_session_id", table_name="chatbot_messages")
    op.drop_table("chatbot_messages")
    op.drop_index(
        "ix_chatbot_sessions_chatbot_started",
        table_name="chatbot_sessions",
    )
    op.drop_table("chatbot_sessions")
    op.drop_table("chatbot_metadata")
    op.drop_table("chatbots")
