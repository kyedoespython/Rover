from sqlalchemy import ForeignKey, UniqueConstraint, func

from main.extensions import db


class FastQuerySection(db.Model):
    __tablename__ = "fastquery_sections"
    __table_args__ = (UniqueConstraint("sort_order", name="uq_fastquery_sections_sort_order"),)

    section_id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    title = db.Column(db.String(128), nullable=False)
    summary = db.Column(db.String(512), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False)
    lesson_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FastQueryProgress(db.Model):
    __tablename__ = "fastquery_progress"

    progress_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    current_section_id = db.Column(db.Integer, ForeignKey("fastquery_sections.section_id", ondelete="SET NULL"), nullable=True)
    demo_database_id = db.Column(db.Integer, ForeignKey("user_schema_databases.schema_database_id", ondelete="SET NULL"), nullable=True, unique=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    last_accessed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    owner = db.relationship("Accounts", back_populates="fastquery_progress")
    current_section = db.relationship(
        "FastQuerySection", foreign_keys=[current_section_id]
    )
    demo_database = db.relationship(
        "UserSchemaDatabase", foreign_keys=[demo_database_id]
    )
    completions = db.relationship(
        "FastQuerySectionCompletion",
        back_populates="progress",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FastQuerySectionCompletion(db.Model):
    __tablename__ = "fastquery_section_completions"
    __table_args__ = (UniqueConstraint("progress_id", "section_id", name="uq_fastquery_completion_progress_section",),)

    completion_id = db.Column(db.Integer, primary_key=True)
    progress_id = db.Column(db.Integer, ForeignKey("fastquery_progress.progress_id", ondelete="CASCADE"), nullable=False)
    section_id = db.Column(db.Integer, ForeignKey("fastquery_sections.section_id", ondelete="CASCADE"), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    progress = db.relationship("FastQueryProgress", back_populates="completions")
    section = db.relationship("FastQuerySection")
