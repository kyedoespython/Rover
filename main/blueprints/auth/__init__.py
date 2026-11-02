from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from . import routes   # import at the BOTTOM to avoid circular imports