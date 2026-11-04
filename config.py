import os
import redis

from dotenv import load_dotenv

load_dotenv()

class Config:

    # session tracking (session key env import)
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # redis config
    REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")

    # redis session config (session)
    SESSION_TYPE = os.environ.get("SESSION_TYPE")
    SESSION_PERMANENT = os.environ.get("SESSION_PERMANENT")
    SESSION_USE_SIGNER = os.environ.get("SESSION_USE_SIGNER")

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")

# running fast database tests
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")