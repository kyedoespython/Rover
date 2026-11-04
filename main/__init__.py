from flask import Flask
from .extensions import db
from .extensions import migrate
from .extensions import login_manager
from .extensions import sess
from .extensions import redis_client

# blueprints
from .blueprints.auth import auth_bp
from .blueprints.home import home_bp

import os

# create the app
def create_app(config_class="config.DevelopmentConfig"):
    app = Flask(__name__)

    # redis config loader from root config class
    app.config.from_object(config_class)

    # start extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    app.config["SESSION_REDIS"] = redis_client

    sess.init_app(app) # redis initialisation

    # register the blueprints for usage
    return app