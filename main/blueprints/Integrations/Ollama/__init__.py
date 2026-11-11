from flask import Blueprint

ollama_bp = Blueprint("Ollama", __name__, url_prefix="/api/ollama")

# Import routes to register their handlers on the blueprint.
from . import routes as _routes  # noqa: F401
