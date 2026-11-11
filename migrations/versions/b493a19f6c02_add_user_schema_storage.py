"""Add user-owned schema documents and summary metadata.

Revision ID: b493a19f6c02
Revises: 6fe27a1b9c40
Create Date: 2026-11-10 21:58:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b493a19f6c02"
down_revision = "6fe27a1b9c40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_schemas",
        sa.Column("schema_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("schema_data", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["accounts.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("schema_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "schema_metadata",
        sa.Column("schema_id", sa.Integer(), nullable=False),
        sa.Column("table_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("column_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("relationship_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("table_names", sa.JSON(), nullable=False),
        sa.Column("data_types", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["schema_id"],
            ["user_schemas.schema_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("schema_id"),
    )


def downgrade():
    op.drop_table("schema_metadata")
    op.drop_table("user_schemas")
