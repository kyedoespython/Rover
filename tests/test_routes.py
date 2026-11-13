from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from flask import Flask
from flask_login import login_required
from flask_migrate import upgrade
from flask_session import Session
from redis import Redis
from werkzeug.security import generate_password_hash

from config import Config
from main import create_app
from main.blueprints.auth import auth_bp
from main.blueprints.home import home_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models import Accounts, Authentication


def test_retired_assistant_routes_are_not_registered():
    app = create_app("testing")
    registered = {rule.rule for rule in app.url_map.iter_rules()}
    assert not any(rule.startswith("/api/ollama") for rule in registered)
    assert "/DesignDashboard/Agents" not in registered
    assert "/Rover/Design/API-Keys" not in registered
    assert "/Rover/Settings/Integrations" not in registered


def test_existing_database_remains_usable_without_removing_stored_data():
    app = create_app("testing")
    with app.app_context():
        with db.engine.connect() as connection:
            connection.connection.driver_connection.create_function(
                "now", 0, lambda: "2026-01-01 00:00:00"
            )
        upgrade(directory="migrations")
        account = Accounts(
            email="migration@example.test",
            username="MigrationUser",
            password="hashed-password",
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        db.session.execute(
            db.text(
                "INSERT INTO user_api_keys "
                "(user_id, key_name, key_type, key_hash, created_at, updated_at) "
                "VALUES (:user_id, 'old key', 'gemini', 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"user_id": account.user_id},
        )
        db.session.commit()
        account.username = "UpdatedUser"
        db.session.commit()
        assert db.session.execute(db.text("SELECT key_name FROM user_api_keys")).scalar_one() == "old key"
        assert db.session.get(Accounts, account.user_id).username == "UpdatedUser"


def test_successful_login_flash_uses_username_from_database():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="login-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()
        account = Accounts(
            email="login@example.com",
            username="RoverUser",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        db.session.add(Authentication(user_id=account.user_id, authenticated=True))
        db.session.commit()

    with app.test_client() as client:
        response = client.post(
            "/Handle_Login",
            data={"username": "RoverUser", "password": "test-password"},
        )
        assert response.status_code == 302
        with client.session_transaction() as session:
            assert ("success", "Welcome back RoverUser!") in session["_flashes"]

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture(params=[False, True])
def redis_login_app(request):
    stored_sessions = {}
    redis_client = Mock(spec=Redis)
    redis_client.get.side_effect = lambda name: stored_sessions.get(name)

    def store_session(name, value, ex):
        stored_sessions[name] = value
        return True

    redis_client.set.side_effect = store_session
    redis_client.delete.side_effect = lambda name: stored_sessions.pop(name, None)

    app = Flask("main")
    app.config.from_object(Config)
    app.config.update(
        TESTING=True,
        SECRET_KEY="login-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SESSION_TYPE="redis",
        SESSION_REDIS=redis_client,
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=request.param,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    Session(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    @app.get("/protected-test")
    @login_required
    def protected_test():
        return "authenticated"

    with app.app_context():
        db.create_all()
        account = Accounts(
            email="remember@example.com",
            username="RememberUser",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        db.session.add(Authentication(user_id=account.user_id, authenticated=True))
        db.session.commit()

    yield app, redis_client, stored_sessions

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_remember_me_uses_three_day_cookie_and_redis_expiry(redis_login_app):
    app, redis_client, stored_sessions = redis_login_app
    remembered = app.test_client()
    ordinary = app.test_client()
    credentials = {"username": "RememberUser", "password": "test-password"}

    before_login = datetime.now(timezone.utc)
    assert remembered.post(
        "/Handle_Login", data={**credentials, "remember_me": "1"}
    ).status_code == 302
    cookie = remembered.get_cookie("session")
    assert cookie is not None
    assert before_login + timedelta(days=3) - timedelta(seconds=2) <= cookie.expires
    assert cookie.expires <= datetime.now(timezone.utc) + timedelta(days=3, seconds=2)
    assert redis_client.set.call_args.kwargs["ex"] == 3 * 24 * 60 * 60
    remembered_key = redis_client.set.call_args.kwargs["name"]

    assert ordinary.post("/Handle_Login", data=credentials).status_code == 302
    ordinary_cookie = ordinary.get_cookie("session")
    assert ordinary_cookie is not None
    assert ordinary_cookie.expires is None
    assert redis_client.set.call_args.kwargs["ex"] == 3 * 24 * 60 * 60

    reopened = app.test_client()
    reopened.set_cookie("session", cookie.value)
    assert reopened.get("/protected-test").status_code == 200
    assert redis_client.set.call_args.kwargs["ex"] == 3 * 24 * 60 * 60

    stored_sessions.pop(remembered_key)
    assert reopened.get("/protected-test").status_code in (401, 302)
    assert ordinary.get("/protected-test").status_code == 200


def test_login_resets_permanence_and_session_version_invalidates_it(redis_login_app):
    app, _, _ = redis_login_app
    client = app.test_client()
    credentials = {"username": "RememberUser", "password": "test-password"}

    client.post("/Handle_Login", data={**credentials, "remember_me": "1"})
    assert client.get_cookie("session").expires is not None
    client.post("/Handle_Login", data=credentials)
    assert client.get_cookie("session").expires is None

    client.post("/Handle_Login", data={**credentials, "remember_me": "1"})
    with app.app_context():
        account = Accounts.query.filter_by(username="RememberUser").one()
        account.session_version += 1
        db.session.commit()
    assert client.get("/protected-test").status_code in (401, 302)


def test_failed_login_does_not_enable_remember_me(redis_login_app):
    app, _, _ = redis_login_app
    client = app.test_client()
    response = client.post(
        "/Handle_Login",
        data={"username": "RememberUser", "password": "wrong", "remember_me": "1"},
    )
    assert response.status_code == 302
    assert client.get_cookie("session").expires is None
    assert client.get("/protected-test").status_code in (401, 302)


@pytest.mark.parametrize(
    "path",
    [
        "/Rover/Login",
        "/Rover/Sign%20Up",
    ],
)
def test_auth_pages_mount_react_forms(redis_login_app, path):
    app, _, _ = redis_login_app
    client = app.test_client()
    page = client.get(path)

    assert page.status_code == 200
    expected_page = b"login" if path == "/Rover/Login" else b"signup"
    assert b'data-page="' + expected_page + b'"' in page.data
    assert b"react/app.js" in page.data
    assert b"scripts/Auth/PasswordToggle.js" not in page.data
