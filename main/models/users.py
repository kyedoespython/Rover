from flask_login import UserMixin
from sqlalchemy import func
from main.extensions import db


class Accounts(db.Model, UserMixin):
    __tablename__ = "accounts"

    user_id = db.Column(db.Integer, primary_key=True)

    authentication_data = db.relationship("Authentication", backref="user_account", uselist=False)
    user_notes = db.relationship("Notes", backref="author", lazy=True)
    user_tickets = db.relationship("Tickets", backref="user", lazy=True)
    schemas = db.relationship("UserSchema", back_populates="owner", cascade="all, delete-orphan", uselist=False, lazy="joined")
    schema_databases = db.relationship("UserSchemaDatabase", back_populates="owner", cascade="all, delete-orphan", lazy="selectin")
    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)
    account_created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    # Incrementing this value invalidates existing Flask-Login sessions.
    session_version = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    last_login_attempt = db.Column(db.DateTime(timezone=True), nullable=True)

    def get_id(self):
        return f"{self.user_id}:{self.session_version}"
