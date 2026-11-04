from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session
from dotenv import load_dotenv

import os
import redis

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
redis_client = redis.from_url(redis_url)

# create a session instance with redis client arg
sess = Session()

@login_manager.user_loader
def load_user(user_id):
    
    from main.models.user import Accounts 
    
    # Return the user object (or None if not found)
    return Accounts.query.get(int(user_id))