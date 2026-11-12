from flask_login import UserMixin
from sqlalchemy import ForeignKey, Index, UniqueConstraint, func

from main.extensions import db


class Accounts(db.Model, UserMixin):
    __tablename__ = "accounts"

    user_id = db.Column(db.Integer, primary_key=True)

    authentication_data = db.relationship(
        "Authentication", backref="user_account", uselist=False
    )

    user_notes = db.relationship("Notes", backref="author", lazy=True)

    user_tickets = db.relationship("Tickets", backref="user", lazy=True)

    schemas = db.relationship(
        "UserSchema",
        back_populates="owner",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )
    schema_databases = db.relationship(
        "UserSchemaDatabase",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)

    account_created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    failed_login_attempts = db.Column(
        db.Integer, default=0, server_default="0", nullable=False
    )
    # Incrementing this value invalidates existing Flask-Login sessions.
    session_version = db.Column(
        db.Integer, default=0, server_default="0", nullable=False
    )

    last_login_attempt = db.Column(db.DateTime(timezone=True), nullable=True)

    def get_id(self):
        return f"{self.user_id}:{self.session_version}"


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    reset_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Authentication(db.Model):
    __tablename__ = "authentication"

    auth_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, ForeignKey("accounts.user_id"), unique=True, nullable=False
    )

    auth_code = db.Column(db.String(256), nullable=True)
    auth_code_expires = db.Column(db.DateTime, nullable=True)
    authenticated = db.Column(db.Boolean, default=False, nullable=False)
    authenticated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Shared across client IPs and reset when a replacement code is issued.
    failed_attempts = db.Column(
        db.Integer, default=0, server_default="0", nullable=False
    )
    last_code_sent_at = db.Column(db.DateTime, nullable=True)


class Tickets(db.Model):
    __tablename__ = "tickets"

    ticket_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), nullable=False)

    ticket_type = db.Column(db.String(64), nullable=False)
    ticket_name = db.Column(db.String(64), nullable=False)
    ticket_content = db.Column(db.String(512), nullable=False)
    ticket_created_at = db.Column(db.DateTime(timezone=True), nullable=False)


class Notes(db.Model):
    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("user_id", "note_name", name="uq_notes_user_name"),
        db.Index("ix_notes_user_modified", "user_id", "note_last_modified_at"),
    )

    note_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), nullable=False)

    note_name = db.Column(db.String(128), nullable=False)
    note_description = db.Column(db.String(512), nullable=False)
    note_content = db.Column(
        db.String(4096), nullable=True
    )  # legacy content, retained for lazy Markdown migration

    note_created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    note_last_modified_at = db.Column(db.DateTime(timezone=True), nullable=False)
    file_metadata = db.relationship(
        "NoteMetadata",
        back_populates="note",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )


class NoteMetadata(db.Model):
    __tablename__ = "note_metadata"

    note_id = db.Column(
        db.Integer, ForeignKey("notes.note_id", ondelete="CASCADE"), primary_key=True
    )
    file_name = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(512), nullable=False, unique=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    content_type = db.Column(
        db.String(64),
        nullable=False,
        default="text/markdown",
        server_default="text/markdown",
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)

    note = db.relationship("Notes", back_populates="file_metadata")


class UserSchema(db.Model):
    __tablename__ = "user_schemas"

    schema_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = db.relationship("Accounts", back_populates="schemas")
    details = db.relationship(
        "SchemaMetadata",
        back_populates="schema",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )


class UserSchemaDatabase(db.Model):
    __tablename__ = "user_schema_databases"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "schema_name",
            name="uq_user_schema_databases_user_name",
        ),
        Index("ix_user_schema_databases_user_updated", "user_id", "updated_at"),
    )

    schema_database_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_name = db.Column(db.String(128), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    database_data = db.Column(db.LargeBinary, nullable=False)
    schema_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = db.relationship("Accounts", back_populates="schema_databases")


class SchemaMetadata(db.Model):
    __tablename__ = "schema_metadata"

    schema_id = db.Column(
        db.Integer,
        ForeignKey("user_schemas.schema_id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    column_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    relationship_count = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    table_names = db.Column(db.JSON, nullable=False)
    data_types = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    schema = db.relationship("UserSchema", back_populates="details")
