from flask import Blueprint

ollama_bp = Blueprint("Ollama", __name__, url_prefix="/api/ollama")

from . import routes
