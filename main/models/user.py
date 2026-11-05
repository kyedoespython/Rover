from main.extensions import db

from datetime import datetime
from datetime import timezone
from sqlalchemy import func, ForeignKey

class Accounts(db.Model):
    __tablename__ = "accounts"

    user_id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(254), unique=True, nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(32), unique=True, nullable=True)
    country_of_origin = db.Column(db.String(64), nullable=False)
    account_created_at = db.Column(db.DateTime, server_default=func.now()) # timestamp
    authentication_data = db.relationship('Authentication', backref='user', uselist=False)

class Authentication(db.Model):
    __tablename__ = "Authentication"

    auth_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey("accounts.user_id"))
    
    auth_code = db.Column(db.String(256), nullable=True)
    auth_code_expires = db.Column(db.DateTime, nullable=True)

    # user starts un authenticated
    authenticated = db.Column(db.Boolean, default=False, nullable=False) # true / false
    authenticated_at = db.Column(db.DateTime, nullable=True) # timestamp