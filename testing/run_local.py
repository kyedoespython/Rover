import argparse
import secrets
import shutil
from pathlib import Path

from flask import Flask
from sqlalchemy.engine import URL
from werkzeug.security import generate_password_hash

from main.blueprints.auth import auth_bp
from main.blueprints.home import home_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models import Accounts, Authentication

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DATABASE = ROOT / "testing" / "schema" / "rover_test.sqlite3"
LOCAL_DATABASE = ROOT / "testing" / "data" / "rover_local.sqlite3"
LOCAL_NOTES = ROOT / "testing" / "data" / "notes"
TEST_USERNAME = "LocalTester"
TEST_PASSWORD = "LocalTest!234"


def create_local_app(reset=False):
    LOCAL_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    if reset and LOCAL_DATABASE.exists():
        LOCAL_DATABASE.unlink()
    if not LOCAL_DATABASE.exists():
        if not SCHEMA_DATABASE.exists():
            raise FileNotFoundError(
                f"{SCHEMA_DATABASE} is missing; create it with "
                "'python -m testing.schema.create_test_database'."
            )
        shutil.copy2(SCHEMA_DATABASE, LOCAL_DATABASE)

    app = Flask(
        __name__,
        template_folder=str(ROOT / "main" / "templates"),
        static_folder=str(ROOT / "main" / "static"),
    )
    app.config.from_mapping(
        DEBUG=False,
        TESTING=False,
        SECRET_KEY=secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=URL.create(
            "sqlite",
            database=str(LOCAL_DATABASE),
        ).render_as_string(hide_password=False),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        NOTE_STORAGE_DIR=str(LOCAL_NOTES),
        PUBLIC_BASE_URL="http://127.0.0.1:5000",
        WTF_CSRF_ENABLED=True,
        RATELIMIT_ENABLED=False,
        SESSION_COOKIE_SECURE=False,
    )

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.Login"
    login_manager.login_message = "Log in with the local test account."
    limiter.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    with app.app_context():
        db.create_all()
        account = Accounts.query.filter_by(username=TEST_USERNAME).first()
        if account is None:
            account = Accounts(
                email="local-test@example.invalid",
                username=TEST_USERNAME,
                password=generate_password_hash(TEST_PASSWORD),
                country_of_origin="United States",
            )
            db.session.add(account)
            db.session.flush()
        authentication = Authentication.query.filter_by(user_id=account.user_id).first()
        if authentication is None:
            authentication = Authentication(
                user_id=account.user_id,
                authenticated=True,
            )
            db.session.add(authentication)
        else:
            authentication.authenticated = True
        db.session.commit()

    return app


def main():
    parser = argparse.ArgumentParser(description="Run Rover locally with an isolated SQLite database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Replace testing/data/rover_local.sqlite3 with a clean schema copy.",
    )
    args = parser.parse_args()
    app = create_local_app(reset=args.reset)
    print(f"Local Rover test app: http://127.0.0.1:5000 (user: {TEST_USERNAME})")
    app.run(host="127.0.0.1", port=5000, use_reloader=False)


if __name__ == "__main__":
    main()
