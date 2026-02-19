from flask import Blueprint

bp = Blueprint("qc", __name__)

from app.blueprints.qc import routes  # noqa: E402,F401
