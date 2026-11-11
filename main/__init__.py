from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
import atexit

from .extensions import db
from .extensions import migrate
from .extensions import login_manager
from .extensions import sess
from .extensions import redis_client
from .extensions import csrf
from .extensions import limiter

# blueprints
from .blueprints.auth import auth_bp
from .blueprints.home import home_bp
from .blueprints.Integrations.Ollama import ollama_bp

# import config map, prod config
from config import CONFIG_MAP, ProductionConfig

import os

# create the app
def create_app(env: str | None = None):

    # find the current environment used, no fallback
    env = env or os.environ.get("APP_ENV")

    # check if env is empty
    # provide runtime error if so
    if env is None:
        raise RuntimeError(
            "APP_ENV is not set. Refusing to start "
            "Set APP_ENV to 'development', 'testing' or 'production' "
            "in your environment or .env file"
        )

    # lookup class inside dispatch table
    config_class = CONFIG_MAP.get(env)
    if config_class is None:
        raise RuntimeError(f"FLASK_ENV {env!r} is not recognised\nChoose from {list(CONFIG_MAP)}")

    # if running the prod env and no screts crash the program
    if config_class is ProductionConfig:
        config_class.load_required()

    # instaniate the app
    app = Flask(__name__)

    # redis config loader from root config class
    app.config.from_object(config_class)
    if config_class is ProductionConfig:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # start extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # initialise csrf protection
    csrf.init_app(app)

    # initialise limiter
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(ollama_bp)

    # login manager section (specific page locks)
    login_manager.init_app(app) # initialise

    login_manager.login_view = "auth.Login" # redirect to login page

    # error messages
    login_manager.login_message = "You must be logged into an account to unlock this page"
    login_manager.login_message_category = "error"

    app.config["SESSION_REDIS"] = redis_client

    sess.init_app(app) # redis initialisation

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

    # register the blueprints for usage
    return app