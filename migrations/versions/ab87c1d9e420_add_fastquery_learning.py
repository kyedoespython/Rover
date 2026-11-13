"""Add FastQuery lessons, learning progress, and per-user demo database marker."""

from alembic import op
import sqlalchemy as sa


revision = "ab87c1d9e420"
down_revision = "f73d2c8a9b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_schema_databases",
        sa.Column(
            "is_fastquery_demo",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_user_schema_databases_fastquery_demo",
        "user_schema_databases",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_fastquery_demo IS TRUE"),
        sqlite_where=sa.text("is_fastquery_demo = 1"),
    )

    op.create_table(
        "fastquery_sections",
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("lesson_data", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("section_id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("sort_order", name="uq_fastquery_sections_sort_order"),
    )

    op.create_table(
        "fastquery_progress",
        sa.Column("progress_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("current_section_id", sa.Integer(), nullable=True),
        sa.Column("demo_database_id", sa.Integer(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
            ["current_section_id"],
            ["fastquery_sections.section_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["demo_database_id"],
            ["user_schema_databases.schema_database_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["accounts.user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("progress_id"),
        sa.UniqueConstraint("demo_database_id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "fastquery_section_completions",
        sa.Column("completion_id", sa.Integer(), nullable=False),
        sa.Column("progress_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
            ["progress_id"],
            ["fastquery_progress.progress_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["fastquery_sections.section_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("completion_id"),
        sa.UniqueConstraint(
            "progress_id",
            "section_id",
            name="uq_fastquery_completion_progress_section",
        ),
    )


def downgrade():
    op.drop_table("fastquery_section_completions")
    op.drop_table("fastquery_progress")
    op.drop_table("fastquery_sections")
    op.drop_index(
        "uq_user_schema_databases_fastquery_demo",
        table_name="user_schema_databases",
    )
    op.drop_column("user_schema_databases", "is_fastquery_demo")
