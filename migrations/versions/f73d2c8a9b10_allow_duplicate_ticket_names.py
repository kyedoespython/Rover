"""Allow support tickets to share a title.

Revision ID: f73d2c8a9b10
Revises: e12a73b4c905
"""
from alembic import op
import sqlalchemy as sa

revision = "f73d2c8a9b10"
down_revision = "e12a73b4c905"
branch_labels = None
depends_on = None


def upgrade():
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("tickets")
    constraint = next(
        (item for item in constraints if item["column_names"] == ["ticket_name"]),
        None,
    )
    if constraint is None:
        raise RuntimeError("The tickets table has no unique constraint on ticket_name")
    with op.batch_alter_table(
        "tickets", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch_op:
        batch_op.drop_constraint(constraint["name"] or "uq_tickets_ticket_name", type_="unique")


def downgrade():
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.create_unique_constraint("uq_tickets_ticket_name", ["ticket_name"])
