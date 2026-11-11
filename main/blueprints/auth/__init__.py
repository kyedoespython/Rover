from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

# Import routes to register their handlers on the blueprint.
from . import routes as _routes  # noqa: F401
