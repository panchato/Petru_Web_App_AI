from flask import Blueprint

bp = Blueprint("fumigation", __name__)

from app.blueprints.fumigation import routes  # noqa: E402,F401
