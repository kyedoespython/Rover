import atexit
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import CONFIG_MAP, ProductionConfig

from .blueprints.auth import auth_bp
from .blueprints.home import home_bp
from .blueprints.Integrations.Ollama import ollama_bp
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
    app.register_blueprint(ollama_bp)

    login_manager.init_app(app)
    login_manager.login_view = "auth.Login"
    login_manager.login_message = (
        "You must be logged into an account to unlock this page"
    )
    login_manager.login_message_category = "error"

    app.config["SESSION_REDIS"] = redis_client
    sess.init_app(app)

    if not app.testing and app.config.get("AGENT_HISTORY_CLEANUP_ENABLED", True):
        from apscheduler.schedulers.background import BackgroundScheduler

        from main.services.agent_history_cleanup import cleanup_expired_agent_history

        def cleanup_agent_history_job():
            with app.app_context():
                deleted_count = cleanup_expired_agent_history()
                if deleted_count:
                    app.logger.info(
                        "Expired %s Triple Rover chat histories.",
                        deleted_count,
                    )

        # Keep background cleanup out of tests to avoid nondeterministic work.
        scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        scheduler.add_job(
            cleanup_agent_history_job,
            trigger="cron",
            hour=3,
            minute=0,
            id="rover_agent_history_cleanup",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.start()
        app.extensions["rover_agent_history_scheduler"] = scheduler
        atexit.register(scheduler.shutdown, wait=False)

    return app
