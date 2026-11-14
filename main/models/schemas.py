from sqlalchemy import ForeignKey, Index, UniqueConstraint, func, text

from main.extensions import db


class UserSchema(db.Model):
    __tablename__ = "user_schemas"

    schema_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    schema_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    owner = db.relationship("Accounts", back_populates="schemas")
    details = db.relationship("SchemaMetadata", back_populates="schema", cascade="all, delete-orphan", uselist=False, lazy="joined")


class UserSchemaDatabase(db.Model):
    __tablename__ = "user_schema_databases"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "schema_name",
            name="uq_user_schema_databases_user_name",
        ),
        Index("ix_user_schema_databases_user_updated", "user_id", "updated_at"),
        Index(
            "uq_user_schema_databases_fastquery_demo",
            "user_id",
            unique=True,
            sqlite_where=text("is_fastquery_demo = 1"),
            postgresql_where=text("is_fastquery_demo IS TRUE"),
        ),
    )

    schema_database_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False)
    schema_name = db.Column(db.String(128), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    database_data = db.Column(db.LargeBinary, nullable=False)
    schema_data = db.Column(db.JSON, nullable=False)
    is_fastquery_demo = db.Column(db.Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    owner = db.relationship("Accounts", back_populates="schema_databases")


class SchemaMetadata(db.Model):
    __tablename__ = "schema_metadata"

    schema_id = db.Column(db.Integer, ForeignKey("user_schemas.schema_id", ondelete="CASCADE"), primary_key=True)
    table_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    column_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    relationship_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    table_names = db.Column(db.JSON, nullable=False)
    data_types = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    schema = db.relationship("UserSchema", back_populates="details")
