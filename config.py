import os
import redis

from dotenv import load_dotenv

load_dotenv()

# shared defaults for all environments
class Config:

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # redis session config (session)
    SESSION_TYPE = os.environ.get("SESSION_TYPE")
    SESSION_PERMANENT = os.environ.get("SESSION_PERMANENT")
    SESSION_USE_SIGNER = os.environ.get("SESSION_USE_SIGNER")

    # cookie settings
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # flask mail config
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = os.environ.get("MAIL_PORT", 587)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    NOTE_STORAGE_DIR = os.environ.get("NOTE_STORAGE_DIR")
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
    OLLAMA_API_KEY_ENCRYPTION_KEY = os.environ.get("OLLAMA_API_KEY_ENCRYPTION_KEY")
    AGENT_HISTORY_CLEANUP_ENABLED = os.environ.get(
        "AGENT_HISTORY_CLEANUP_ENABLED",
        "true",
    ).lower() == "true"

# local machine config
class DevelopmentConfig(Config):
    # enables werkzeug interactive debugger only for dev config
    DEBUG = True

    # session tracking (session key env import), dev only (fallback not for prod) 
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret")

    # Get the postgreSQL database link with no fallback
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # Get the redis url, fallback uses localhost, dev uses same fallback
    REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")

# running fast database tests
class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test-secret"

    # an in memory database using sqlite3, wiped at the end of a test
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # points at local docker container, later fakeredis will be setup
    REDIS_URL = "redis://127.0.0.1:6379"

# deployment config (important!)
class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def load_required(cls):
        # fetch required values
        secret = os.environ.get("SECRET_KEY")
        db_uri = os.environ.get("DATABASE_URL")
        redis_url = os.environ.get("REDIS_URL")

        if not secret or len(secret) < 32:
            raise RuntimeError (
                "SECRET_KEY missing or too short, Generate a secret key with: "
                "python -c 'import secrets; print(secrets.token_hex(32))'"
            )

        if not db_uri:
            raise RuntimeError("DATABASE_URL env variable is required")
        if not redis_url:
            raise RuntimeError("REDIS_URL env variable is required")

        # class vars inside the Prod config
        cls.SECRET_KEY = secret
        cls.SQLALCHEMY_DATABASE_URI = db_uri
        cls.REDIS_URL = redis_url

# dispatch table for create app function simplified
CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
