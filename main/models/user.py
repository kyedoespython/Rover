from flask_login import UserMixin
from sqlalchemy import ForeignKey, UniqueConstraint, func

from main.extensions import db


class Accounts(db.Model, UserMixin):
    __tablename__ = "accounts"

    user_id = db.Column(db.Integer, primary_key=True)

    authentication_data = db.relationship(
        "Authentication", backref="user_account", uselist=False
    )

    user_notes = db.relationship("Notes", backref="author", lazy=True)

    user_tickets = db.relationship("Tickets", backref="user", lazy=True)

    api_keys = db.relationship(
        "UserApiKey",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="UserApiKey.user_id",
    )
    chatbot = db.relationship(
        "Chatbot",
        back_populates="owner",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    rover_agents = db.relationship(
        "RoverAgent",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    schemas = db.relationship(
        "UserSchema",
        back_populates="owner",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)
    ollama_model = db.Column(db.String(128), nullable=True)
    active_ollama_api_key_id = db.Column(db.Integer, nullable=True)

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
    ticket_name = db.Column(db.String(64), nullable=False, unique=True)
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


class UserApiKey(db.Model):
    __tablename__ = "user_api_keys"
    __table_args__ = (
        db.UniqueConstraint("user_id", "key_name", name="uq_user_api_keys_user_name"),
        db.Index("ix_user_api_keys_user_created", "user_id", "created_at"),
    )

    api_key_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    key_name = db.Column(db.String(128), nullable=False)
    key_type = db.Column(db.String(32), nullable=False)
    key_hash = db.Column(db.String(512), nullable=False)
    key_ciphertext = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False)

    owner = db.relationship(
        "Accounts",
        back_populates="api_keys",
        foreign_keys=[user_id],
    )


class Chatbot(db.Model):
    __tablename__ = "chatbots"

    chatbot_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("accounts.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    chatbot_name = db.Column(db.String(64), nullable=False, default="Rover AI")
    model_name = db.Column(db.String(128), nullable=False)
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

    owner = db.relationship("Accounts", back_populates="chatbot")
    configuration = db.relationship(
        "ChatbotMetadata",
        back_populates="chatbot",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )
    sessions = db.relationship(
        "ChatbotSession",
        back_populates="chatbot",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )


class ChatbotMetadata(db.Model):
    __tablename__ = "chatbot_metadata"

    chatbot_id = db.Column(
        db.Integer,
        ForeignKey("chatbots.chatbot_id", ondelete="CASCADE"),
        primary_key=True,
    )
    allow_folder_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    allow_folder_write = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    chatbot = db.relationship("Chatbot", back_populates="configuration")


class ChatbotSession(db.Model):
    __tablename__ = "chatbot_sessions"
    __table_args__ = (
        db.Index("ix_chatbot_sessions_chatbot_started", "chatbot_id", "started_at"),
    )

    session_id = db.Column(db.String(36), primary_key=True)
    chatbot_id = db.Column(
        db.Integer,
        ForeignKey("chatbots.chatbot_id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_activity_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    chatbot = db.relationship("Chatbot", back_populates="sessions")
    messages = db.relationship(
        "ChatbotMessage",
        back_populates="chatbot_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )


class ChatbotMessage(db.Model):
    __tablename__ = "chatbot_messages"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chatbot_messages_role",
        ),
        db.Index("ix_chatbot_messages_session_id", "session_id", "message_id"),
    )

    message_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.String(36),
        ForeignKey("chatbot_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    chatbot_session = db.relationship("ChatbotSession", back_populates="messages")


class RoverAgent(db.Model):
    __tablename__ = "rover_agent"
    __table_args__ = (
        db.UniqueConstraint("user_id", "slot_number", name="uq_rover_agent_user_slot"),
        db.CheckConstraint(
            "slot_number BETWEEN 1 AND 3", name="ck_rover_agent_slot_number"
        ),
        db.Index("ix_rover_agent_user_id", "user_id"),
    )

    agent_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False
    )

    # Each account can use one agent in each of the three defined slots.
    slot_number = db.Column(db.Integer, nullable=False)

    agent_name = db.Column(db.String(64), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = db.relationship("Accounts", back_populates="rover_agents")
    configuration = db.relationship(
        "RoverAgentMetadata",
        back_populates="agent",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )
    chat_session = db.relationship(
        "RoverAgentSession",
        back_populates="agent",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )


class RoverAgentMetadata(db.Model):
    __tablename__ = "rover_agent_metadata"

    agent_id = db.Column(
        db.Integer,
        ForeignKey("rover_agent.agent_id", ondelete="CASCADE"),
        primary_key=True,
    )

    system_prompt = db.Column(db.Text, nullable=False, default="", server_default="")
    temperature = db.Column(db.Float, nullable=False, default=0.7, server_default="0.7")

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    agent = db.relationship("RoverAgent", back_populates="configuration")


class RoverAgentSession(db.Model):
    __tablename__ = "rover_agent_sessions"
    __table_args__ = (
        db.Index("ix_rover_agent_sessions_first_message_at", "first_message_at"),
    )

    session_id = db.Column(db.String(36), primary_key=True)

    agent_id = db.Column(
        db.Integer,
        ForeignKey("rover_agent.agent_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Starts the seven-day retention window on the first successful chat.
    first_message_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Tracks activity without extending the first-chat retention window.
    last_activity_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    agent = db.relationship("RoverAgent", back_populates="chat_session")
    messages = db.relationship(
        "RoverAgentMessage",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )


class RoverAgentMessage(db.Model):
    __tablename__ = "rover_agent_messages"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_rover_agent_messages_role"
        ),
        db.Index("ix_rover_agent_messages_session_id", "session_id", "message_id"),
    )

    message_id = db.Column(db.Integer, primary_key=True)

    session_id = db.Column(
        db.String(36),
        ForeignKey("rover_agent_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chat_session = db.relationship("RoverAgentSession", back_populates="messages")


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
