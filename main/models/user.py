from main.extensions import db
from flask_login import UserMixin
from sqlalchemy import func, ForeignKey, UniqueConstraint

class Accounts(db.Model, UserMixin):
    
    __tablename__ = "accounts"

    # primary key to store users id's
    user_id = db.Column(db.Integer, primary_key=True)
    
    # creates a link between the foreign key (auth_id) to (user_id)
    authentication_data = db.relationship('Authentication', backref='user_account', uselist=False)

    # creates a link between the foreign key (note_id) to (user_id)
    user_notes = db.relationship('Notes', backref='author', lazy=True)

    # creates a link between the (ticket_id) and the (user_id)
    user_tickets = db.relationship('Tickets', backref='user', lazy=True)

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

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)
    ollama_model = db.Column(db.String(128), nullable=True)
    active_ollama_api_key_id = db.Column(db.Integer, nullable=True)

    # timestamp uses server_default so postgres fills it in automatically and avoids crashes
    account_created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False) # timestamp

    # store the amount of failed login attempts the user has had, defaulted to no failed login attempts
    failed_login_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)

    # timestamp to store the last known login attempt of the user
    # starts empty and filled only when the user attempts to login / logs into there account
    last_login_attempt = db.Column(db.DateTime(timezone=True), nullable=True)

    # required for flask_login
    def get_id(self):
        return str(self.user_id)

class Authentication(db.Model):

    __tablename__ = "authentication"

    # main authenctication id
    auth_id = db.Column(db.Integer, primary_key=True)

    # user_id connected to one single auth_id as a one to one relationship (unique=True sets as one row for auth)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), unique=True, nullable=False)

    # auth_code stores the auth code
    auth_code = db.Column(db.String(256), nullable=True)
    
    # auth_code_expires stores the 10 minute count to expiry, start off empty
    auth_code_expires = db.Column(db.DateTime, nullable=True)

    # user starts un authenticated, then if authenticated gets timestamped
    authenticated = db.Column(db.Boolean, default=False, nullable=False) # show yes or now on a users auth status

    # timestamp for storing the date and time of the authentication of the user account
    authenticated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # store failed attempts to authenticate, default to no failed attempts, then it adds up per failed attempt
    failed_attempts = db.Column(db.Integer, default=0, server_default="0", nullable=False)

    # store the timestamp of when the last auth code was sent, can be null if there was no auth code sent at all
    last_code_sent_at = db.Column(db.DateTime, nullable=True)

class Tickets(db.Model):

    __tablename__ = "tickets"

    # ticket id to store the id for the whole ticket
    ticket_id = db.Column(db.Integer, primary_key=True)

    # foreign key one user to many tickets (unique is false so tickets can have the same user_id)
    user_id = db.Column(db.Integer, ForeignKey('accounts.user_id'), nullable=False)

    ticket_type = db.Column(db.String(64), nullable=False) # stores what type of the ticket has been created
    ticket_name = db.Column(db.String(64), nullable=False, unique=True) # stores the name of the ticket
    ticket_content = db.Column(db.String(512), nullable=False) # stores the actual ticket content

    # timestamp for when the user created the ticket
    ticket_created_at = db.Column(db.DateTime(timezone=True), nullable=False)

class Notes(db.Model):

    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("user_id", "note_name", name="uq_notes_user_name"),
        db.Index("ix_notes_user_modified", "user_id", "note_last_modified_at"),
    )

    # id to store the note id for the whole note section
    note_id = db.Column(db.Integer, primary_key=True)

    # foreign key representing the one to many relationship between one user -> many notes
    user_id = db.Column(db.Integer, ForeignKey('accounts.user_id'), nullable=False)

    note_name = db.Column(db.String(128), nullable=False) # stores the name of the note given by the user
    note_description = db.Column(db.String(512), nullable=False) # stores the description of the note provides by the user
    note_content = db.Column(db.String(4096), nullable=True) # legacy content, retained for lazy Markdown migration

    note_created_at = db.Column(db.DateTime(timezone=True), nullable=False) # stores a timestamp of when the note was created
    note_last_modified_at = db.Column(db.DateTime(timezone=True), nullable=False) # stores a timestamp of the last time a specific note was modified by the user

    # note to note_metadata of the file relationship
    file_metadata = db.relationship("NoteMetadata", back_populates="note", cascade="all, delete-orphan", uselist=False, lazy="joined")


class NoteMetadata(db.Model):

    __tablename__ = "note_metadata"

    note_id = db.Column(db.Integer, ForeignKey("notes.note_id", ondelete="CASCADE"), primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(512), nullable=False, unique=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    content_type = db.Column(db.String(64), nullable=False, default="text/markdown", server_default="text/markdown")
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
        db.CheckConstraint("slot_number BETWEEN 1 AND 3", name="ck_rover_agent_slot_number"),
        db.Index("ix_rover_agent_user_id", "user_id"),
    )

    # Identifies one of the user's three agent slots.
    agent_id = db.Column(db.Integer, primary_key=True)

    # Connects this slot to its owning account.
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False)

    # Fixes each account to exactly three possible slot numbers.
    slot_number = db.Column(db.Integer, nullable=False)

    # Stores the user's display name and selected Ollama model.
    agent_name = db.Column(db.String(64), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)

    # Tracks when the slot was created or last configured.
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relates this slot to its owner, configuration, and retained chat.
    owner = db.relationship("Accounts", back_populates="rover_agents")
    configuration = db.relationship("RoverAgentMetadata", back_populates="agent", cascade="all, delete-orphan", uselist=False, lazy="joined")
    chat_session = db.relationship("RoverAgentSession", back_populates="agent", cascade="all, delete-orphan", uselist=False, passive_deletes=True)


class RoverAgentMetadata(db.Model):

    __tablename__ = "rover_agent_metadata"

    # Uses the agent id as the metadata row's identity and foreign key.
    agent_id = db.Column(db.Integer, ForeignKey("rover_agent.agent_id", ondelete="CASCADE"), primary_key=True)

    # Stores optional per-agent system instructions and generation settings.
    system_prompt = db.Column(db.Text, nullable=False, default="", server_default="")
    temperature = db.Column(db.Float, nullable=False, default=0.7, server_default="0.7")

    # Tracks the last configuration update.
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Links settings back to their agent slot.
    agent = db.relationship("RoverAgent", back_populates="configuration")


class RoverAgentSession(db.Model):

    __tablename__ = "rover_agent_sessions"
    __table_args__ = (db.Index("ix_rover_agent_sessions_first_message_at", "first_message_at"),)

    # Identifies one retained conversation for an agent slot.
    session_id = db.Column(db.String(36), primary_key=True)

    # Allows only one current conversation per agent slot.
    agent_id = db.Column(db.Integer, ForeignKey("rover_agent.agent_id", ondelete="CASCADE"), nullable=False, unique=True)

    # Starts the seven-day retention window on the first successful chat.
    first_message_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Tracks activity without extending the first-chat retention window.
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relates the conversation to its agent and transcript.
    agent = db.relationship("RoverAgent", back_populates="chat_session")
    messages = db.relationship("RoverAgentMessage", back_populates="chat_session", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic")


class RoverAgentMessage(db.Model):

    __tablename__ = "rover_agent_messages"
    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'assistant')", name="ck_rover_agent_messages_role"),
        db.Index("ix_rover_agent_messages_session_id", "session_id", "message_id"),
    )

    # Identifies one ordered transcript message.
    message_id = db.Column(db.Integer, primary_key=True)

    # Connects the message to its agent conversation.
    session_id = db.Column(db.String(36), ForeignKey("rover_agent_sessions.session_id", ondelete="CASCADE"), nullable=False)

    # Restricts persisted transcript entries to chat roles.
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # Records when this transcript entry was saved.
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    # Links the message back to its conversation.
    chat_session = db.relationship("RoverAgentSession", back_populates="messages")