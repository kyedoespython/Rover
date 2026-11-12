import pytest

from config import _environment_boolean


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
