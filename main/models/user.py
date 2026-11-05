from main.extensions import db

from datetime import datetime
from datetime import timezone

class Accounts(db.Model):
    __tablename__ = "accounts"

    # id's
    user_id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now())