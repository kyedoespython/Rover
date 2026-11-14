"""Add persistent per-user workspace projects.

Revision ID: 35c1a8e7d4b2
Revises: f73d2c8a9b10
"""
from alembic import op
import sqlalchemy as sa


revision = "35c1a8e7d4b2"
down_revision = "ab87c1d9e420"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_projects",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["accounts.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_workspace_projects_user_name"),
    )
    op.create_index("ix_workspace_projects_user_id", "workspace_projects", ["user_id"])


def downgrade():
    op.drop_index("ix_workspace_projects_user_id", table_name="workspace_projects")
    op.drop_table("workspace_projects")
