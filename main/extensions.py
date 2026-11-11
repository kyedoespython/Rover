from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session

# Flask_WTF, using for CSRF protection
from flask_wtf.csrf import CSRFProtect

# rate limiter packages
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from dotenv import load_dotenv

import os
import redis

# load up the packages
load_dotenv()
db = SQLAlchemy()
migrate = Migrate()

# init of the csrf protection package
csrf = CSRFProtect()

# init of the login manager package from flask_login
login_manager = LoginManager()

redis_url = os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379"
redis_client = redis.from_url(redis_url)

# create a session instance with redis client arg
sess = Session()

limiter = Limiter (
    
    key_func=get_remote_address,
    storage_uri=redis_url,

    # global limits on requests / use if need
    # default_limits=["100 per day", "50 per hour"]
)

@login_manager.user_loader
def load_user(user_id):
    from main.models.user import Accounts

    account_id, separator, raw_session_version = user_id.partition(":")
    try:
        user = Accounts.query.get(int(account_id))
    except ValueError:
        return None

    if user is None:
        return None
    if not separator:
        return user if user.session_version == 0 else None
    if not raw_session_version.isdecimal():
        return None
    return user if user.session_version == int(raw_session_version) else None