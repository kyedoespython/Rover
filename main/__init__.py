from flask import Flask
from .extensions import db, migrate, login_manager

# blueprints
from .blueprints.auth import auth_bp
from .blueprints.home import home_bp


def create_app(config_class="config.DevelopmentConfig"):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    return app