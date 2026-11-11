import pytest

from config import ProductionConfig, _environment_boolean


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("false", False),
        ("0", False),
        ("true", True),
        ("1", True),
    ],
)
def test_environment_boolean_parses_common_values(monkeypatch, value, expected):
    monkeypatch.setenv("TEST_BOOLEAN", value)

    assert _environment_boolean("TEST_BOOLEAN", not expected) is expected


def test_environment_boolean_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("TEST_BOOLEAN", "sometimes")

    with pytest.raises(RuntimeError, match="TEST_BOOLEAN"):
        _environment_boolean("TEST_BOOLEAN", False)


def _set_required_production_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://rover:password@db.example.test/rover",
    )
    monkeypatch.setenv("REDIS_URL", "redis://redis.example.test:6379/0")
    monkeypatch.setenv("SESSION_TYPE", "redis")
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://rover.example.test")


def test_production_defaults_ollama_to_cloud(monkeypatch):
    _set_required_production_environment(monkeypatch)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    class IsolatedProductionConfig(ProductionConfig):
        pass

    IsolatedProductionConfig.load_required()

    assert IsolatedProductionConfig.OLLAMA_BASE_URL == "https://ollama.com"


def test_production_respects_configured_ollama_endpoint(monkeypatch):
    _set_required_production_environment(monkeypatch)
    custom_endpoint = "http://ollama.internal:11434"
    monkeypatch.setenv("OLLAMA_BASE_URL", custom_endpoint)

    class IsolatedProductionConfig(ProductionConfig):
        pass

    IsolatedProductionConfig.load_required()

    assert IsolatedProductionConfig.OLLAMA_BASE_URL == custom_endpoint
