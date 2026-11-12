import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _environment_boolean(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be set to a boolean value")


# Settings shared by development, tests, and production.
class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_TYPE = os.environ.get("SESSION_TYPE") or "redis"
    SESSION_PERMANENT = _environment_boolean("SESSION_PERMANENT", False)
    SESSION_USE_SIGNER = _environment_boolean("SESSION_USE_SIGNER", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=3)

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    RESEND_FROM_EMAIL = os.environ.get(
        "RESEND_FROM_EMAIL",
        "Rover <noreply@rover-solutions.com>",
    )
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL") or (
        f"https://{os.environ['ROVER_DOMAIN'].strip('/')}"
        if os.environ.get("ROVER_DOMAIN")
        else None
    )
    NOTE_STORAGE_DIR = os.environ.get("NOTE_STORAGE_DIR")
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
    OLLAMA_API_KEY_ENCRYPTION_KEY = os.environ.get("OLLAMA_API_KEY_ENCRYPTION_KEY")
    AGENT_HISTORY_CLEANUP_ENABLED = (
        os.environ.get(
            "AGENT_HISTORY_CLEANUP_ENABLED",
            "true",
        ).lower()
        == "true"
    )


# Development-only defaults. Production startup requires real deployment secrets.
class DevelopmentConfig(Config):
    DEBUG = True

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    REDIS_URL = os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379"


# In-memory settings keep database tests isolated and fast.
class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    REDIS_URL = "redis://127.0.0.1:6379"


# Validate deployment secrets before creating a production app.
class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def load_required(cls):
        secret = os.environ.get("SECRET_KEY")
        db_uri = os.environ.get("DATABASE_URL")
        redis_url = os.environ.get("REDIS_URL")
        session_type = (os.environ.get("SESSION_TYPE") or "redis").strip().lower()
        resend_api_key = os.environ.get("RESEND_API_KEY")
        public_base_url = os.environ.get("PUBLIC_BASE_URL")
        rover_domain = os.environ.get("ROVER_DOMAIN")
        ollama_base_url = os.environ.get("OLLAMA_BASE_URL")

        if not secret or len(secret) < 32:
            raise RuntimeError(
                "SECRET_KEY missing or too short, Generate a secret key with: "
                "python -c 'import secrets; print(secrets.token_hex(32))'"
            )

        if not db_uri:
            raise RuntimeError("DATABASE_URL env variable is required")
        if not redis_url:
            raise RuntimeError("REDIS_URL env variable is required")
        if session_type != "redis":
            raise RuntimeError("SESSION_TYPE must be 'redis' in production")
        if not resend_api_key:
            raise RuntimeError("RESEND_API_KEY env variable is required")
        if not public_base_url and not rover_domain:
            raise RuntimeError(
                "PUBLIC_BASE_URL or ROVER_DOMAIN is required for password reset links"
            )

        cls.SECRET_KEY = secret
        cls.SQLALCHEMY_DATABASE_URI = db_uri
        cls.REDIS_URL = redis_url
        cls.SESSION_TYPE = session_type
        cls.RESEND_API_KEY = resend_api_key
        cls.PUBLIC_BASE_URL = public_base_url or f"https://{rover_domain.strip('/')}"
        # Hosted production apps normally have no local Ollama daemon.
        cls.OLLAMA_BASE_URL = ollama_base_url or "https://ollama.com"


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
