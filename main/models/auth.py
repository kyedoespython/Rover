from sqlalchemy import ForeignKey

from main.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    reset_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Authentication(db.Model):
    __tablename__ = "authentication"

    auth_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), unique=True, nullable=False)
    auth_code = db.Column(db.String(256), nullable=True)
    auth_code_expires = db.Column(db.DateTime, nullable=True)
    authenticated = db.Column(db.Boolean, default=False, nullable=False)
    authenticated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Shared across client IPs and reset when a replacement code is issued.
    failed_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)
    last_code_sent_at = db.Column(db.DateTime, nullable=True)
