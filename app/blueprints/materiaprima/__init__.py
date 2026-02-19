from flask import Blueprint

bp = Blueprint("materiaprima", __name__)

from app.blueprints.materiaprima import routes  # noqa: E402,F401
