from sqlalchemy import ForeignKey, UniqueConstraint

from main.extensions import db


class Notes(db.Model):
    __tablename__ = "notes"
    __table_args__ = (UniqueConstraint("user_id", "note_name", name="uq_notes_user_name"), db.Index("ix_notes_user_modified", "user_id", "note_last_modified_at"))

    note_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"), nullable=False)
    note_name = db.Column(db.String(128), nullable=False)
    note_description = db.Column(db.String(512), nullable=False)
    note_content = db.Column(db.String(4096), nullable=True)  # legacy content, retained for lazy Markdown migration
    note_created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    note_last_modified_at = db.Column(db.DateTime(timezone=True), nullable=False)
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
