import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import CONFIG_MAP, ProductionConfig

from .blueprints.auth import auth_bp
from .blueprints.home import home_bp
from .extensions import csrf, db, limiter, login_manager, migrate, redis_client, sess


def create_app(env: str | None = None):
    """Create and configure the Flask application for one environment."""

    env = env or os.environ.get("APP_ENV")
    if env is None:
        raise RuntimeError(
            "APP_ENV is not set. Refusing to start "
            "Set APP_ENV to 'development', 'testing' or 'production' "
            "in your environment or .env file"
        )

    config_class = CONFIG_MAP.get(env)
    if config_class is None:
        raise RuntimeError(
            f"APP_ENV {env!r} is not recognized\nChoose from {list(CONFIG_MAP)}"
        )

    if config_class is ProductionConfig:
        config_class.load_required()

    app = Flask(__name__)
    app.config.from_object(config_class)
    if config_class is ProductionConfig:
        # Respect Render's forwarded scheme and client IP behind its proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    login_manager.init_app(app)
    login_manager.login_view = "auth.Login"
    login_manager.login_message = (
        "You must be logged into an account to unlock this page"
    )
    login_manager.login_message_category = "error"

    app.config["SESSION_REDIS"] = redis_client
    sess.init_app(app)

    return app
