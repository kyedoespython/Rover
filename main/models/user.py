from main.extensions import db

from datetime import datetime
from datetime import timezone

class Accounts(db.Model):
    __tablename__ = "accounts"

    # id's
    user_id = db.Column(db.Integer, primary_key=True)

    user_email = db.Column(db.String(254), unique=True, nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True) # optional phone number
    country_of_origin = db.Column(db.String(64), nullable=False) # for page language setting decisions
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

class Actions(db.Model):
    __tablename__ = "actions"

    # id's
    action_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("accounts.user_id"), nullable=False)

    is_running = db.Column(db.Boolean, default=False, nullable=False)
    action_type = db.Column(db.String(64), nullable=False)
    action_name = db.Column(db.String(64), nullable=False)
    action_description = db.Column(db.String(512), nullable=True)
    action_performed_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class Logs(db.Model):
    __tablename__ = "user_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("accounts.user_id"), nullable=False)
    log_title = db.Column(db.String(64), nullable=False)
    log_description = db.Column(db.String(512), nullable=True)
    log_contents = db.Column(db.String(512), nullable=True)
    log_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class Prompts(db.Model):
    __tablename__ = "user_prompts"

    # id's
    
    # primary key
    prompt_id = db.Column(db.Integer, primary_key=True)

    # prompt is connected to a user
    user_id = db.Column(db.Integer, db.ForeignKey("accounts.user_id"), nullable=False)

    prompt_text = db.Column(db.String(512), nullable=False)
    prompt_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
