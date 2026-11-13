import os

import redis
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# Extension instances are bound to Flask apps in the application factory.
load_dotenv()
db = SQLAlchemy()
migrate = Migrate()

csrf = CSRFProtect()
login_manager = LoginManager()

redis_url = os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379"
redis_client = redis.from_url(redis_url)

sess = Session()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url,
)


@login_manager.user_loader
def load_user(user_id):
    from main.models.users import Accounts

    account_id, separator, raw_session_version = user_id.partition(":")
    try:
        user = Accounts.query.get(int(account_id))
    except ValueError:
        return None

    if user is None:
        return None
    # Legacy session IDs have no version; honor them only before invalidation.
    if not separator:
        return user if user.session_version == 0 else None
    if not raw_session_version.isdecimal():
        return None
    return user if user.session_version == int(raw_session_version) else None
