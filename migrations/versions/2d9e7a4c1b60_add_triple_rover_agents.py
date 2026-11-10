"""Add three configurable Rover agents and expiring chat history.

Revision ID: 2d9e7a4c1b60
Revises: 1c4a7b9d2e60
Create Date: 2026-11-10 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2d9e7a4c1b60"
down_revision = "1c4a7b9d2e60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rover_agent",
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slot_number BETWEEN 1 AND 3", name="ck_rover_agent_slot_number"),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id"),
        sa.UniqueConstraint("user_id", "slot_number", name="uq_rover_agent_user_slot"),
    )
    op.create_index("ix_rover_agent_user_id", "rover_agent", ["user_id"], unique=False)

    op.create_table(
        "rover_agent_metadata",
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), server_default="", nullable=False),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["rover_agent.agent_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id"),
    )

    op.create_table(
        "rover_agent_sessions",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["rover_agent.agent_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index(
        "ix_rover_agent_sessions_first_message_at",
        "rover_agent_sessions",
        ["first_message_at"],
        unique=False,
    )

    op.create_table(
        "rover_agent_messages",
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_rover_agent_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["rover_agent_sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_rover_agent_messages_session_id",
        "rover_agent_messages",
        ["session_id", "message_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_rover_agent_messages_session_id", table_name="rover_agent_messages")
    op.drop_table("rover_agent_messages")
    op.drop_index("ix_rover_agent_sessions_first_message_at", table_name="rover_agent_sessions")
    op.drop_table("rover_agent_sessions")
    op.drop_table("rover_agent_metadata")
    op.drop_index("ix_rover_agent_user_id", table_name="rover_agent")
    op.drop_table("rover_agent")
