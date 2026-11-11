"""Store user schema databases as SQLite files.

Revision ID: c5d8e2a41f90
Revises: 7c2d9a41e6b3
Create Date: 2026-11-11 11:24:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c5d8e2a41f90"
down_revision = "7c2d9a41e6b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_schema_databases",
        sa.Column("schema_database_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("database_data", sa.LargeBinary(), nullable=False),
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
        sa.PrimaryKeyConstraint("schema_database_id"),
        sa.UniqueConstraint(
            "user_id",
            "schema_name",
            name="uq_user_schema_databases_user_name",
        ),
    )
    op.create_index(
        "ix_user_schema_databases_user_updated",
        "user_schema_databases",
        ["user_id", "updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_user_schema_databases_user_updated",
        table_name="user_schema_databases",
    )
    op.drop_table("user_schema_databases")
