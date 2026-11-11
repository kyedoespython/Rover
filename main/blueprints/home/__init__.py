from flask import Blueprint

home_bp = Blueprint("home", __name__)

# Import routes to register their handlers on the blueprint.
from . import routes as _routes  # noqa: F401
