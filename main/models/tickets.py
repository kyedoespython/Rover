from sqlalchemy import ForeignKey

from main.extensions import db


class Tickets(db.Model):
    __tablename__ = "tickets"

    ticket_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), nullable=False)
    ticket_type = db.Column(db.String(64), nullable=False)
    ticket_name = db.Column(db.String(64), nullable=False)
    ticket_content = db.Column(db.String(512), nullable=False)
    ticket_created_at = db.Column(db.DateTime(timezone=True), nullable=False)
