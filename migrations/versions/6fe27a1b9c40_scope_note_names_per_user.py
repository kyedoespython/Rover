"""Scope note names to their owner.

Revision ID: 6fe27a1b9c40
Revises: 2d9e7a4c1b60
Create Date: 2026-11-10 06:23:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "6fe27a1b9c40"
down_revision = "2d9e7a4c1b60"
branch_labels = None
depends_on = None


def _note_name_constraint_name(bind):
    constraints = sa.inspect(bind).get_unique_constraints("notes")
    for constraint in constraints:
        if constraint["column_names"] == ["note_name"]:
            return constraint["name"] or "uq_notes_note_name"
    raise RuntimeError("The notes table has no unique constraint on note_name")


def upgrade():
    bind = op.get_bind()
    old_constraint = _note_name_constraint_name(bind)
    op.drop_index("ix_notes_user_id", table_name="notes")
    with op.batch_alter_table(
        "notes",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        batch_op.drop_constraint(old_constraint, type_="unique")
        batch_op.create_unique_constraint(
            "uq_notes_user_name",
            ["user_id", "note_name"],
        )
    op.create_index(
        "ix_notes_user_modified",
        "notes",
        ["user_id", "note_last_modified_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_notes_user_modified", table_name="notes")
    with op.batch_alter_table(
        "notes",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        batch_op.drop_constraint("uq_notes_user_name", type_="unique")
        batch_op.create_unique_constraint("uq_notes_note_name", ["note_name"])
    op.create_index("ix_notes_user_id", "notes", ["user_id"], unique=False)
