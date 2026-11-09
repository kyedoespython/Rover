from flask import Flask

from .extensions import db
from .extensions import migrate
from .extensions import login_manager
from .extensions import sess, mail
from .extensions import redis_client
from .extensions import csrf
from .extensions import limiter

# blueprints
from .blueprints.auth import auth_bp
from .blueprints.home import home_bp

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

    # start extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # initialise csrf protection
    csrf.init_app(app)

    # initialise limiter
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    # login manager section (specific page locks)
    login_manager.init_app(app) # initialise

    login_manager.login_view = "auth.Login" # redirect to login page

    # error messages
    login_manager.login_message = "You must be logged into an account to unlock this page"
    login_manager.login_message_category = "error"

    app.config["SESSION_REDIS"] = redis_client

    mail.init_app(app) # flask mail initialisation
    sess.init_app(app) # redis initialisation

    # register the blueprints for usage
    return app