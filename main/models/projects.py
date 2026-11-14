from datetime import datetime, timezone

from sqlalchemy import ForeignKey, UniqueConstraint

from main.extensions import db


class WorkspaceProject(db.Model):
    __tablename__ = "workspace_projects"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_workspace_projects_user_name"),)

    project_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    items = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
