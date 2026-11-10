"""Add Markdown file metadata for notes.

Revision ID: 93f2c0e1a7b4
Revises: 26784f514e0b
Create Date: 2026-11-09 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "93f2c0e1a7b4"
down_revision = "26784f514e0b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_notes_user_id", "notes", ["user_id"], unique=False)
    op.create_table(
        "note_metadata",
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=64),
            server_default="text/markdown",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.note_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("note_id"),
        sa.UniqueConstraint("relative_path"),
    )


def downgrade():
    op.drop_table("note_metadata")
    op.drop_index("ix_notes_user_id", table_name="notes")
