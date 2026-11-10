from flask import Flask
from werkzeug.security import generate_password_hash

from main.blueprints.auth import auth_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models.user import Accounts, Authentication


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
            assert ("success", "Welcome to Rover RoverUser!") in session["_flashes"]

    with app.app_context():
        db.session.remove()
        db.drop_all()
