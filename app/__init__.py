import os
import uuid
import logging
from flask import Flask
from flask import abort, request, g, has_request_context
from app.config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.orm import Session
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
app.config["DASHBOARD_LAST_COMMIT_AT"] = datetime.utcnow().isoformat()
for path_key in ("UPLOAD_ROOT", "UPLOAD_PATH_IMAGE", "UPLOAD_PATH_PDF"):
    os.makedirs(app.config[path_key], exist_ok=True)


class _RequestIdLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        return True


def _configure_logging(flask_app):
    level_name = str(flask_app.config.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
    )
    request_id_filter = _RequestIdLogFilter()

    if not flask_app.logger.handlers:
        flask_app.logger.addHandler(logging.StreamHandler())

    for handler in flask_app.logger.handlers:
        handler.setFormatter(formatter)
        if not any(isinstance(existing_filter, _RequestIdLogFilter) for existing_filter in handler.filters):
            handler.addFilter(request_id_filter)

    flask_app.logger.setLevel(level)


_configure_logging(app)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = "login"
migrate = Migrate(app, db)
csrf = CSRFProtect(app)


@app.before_request
def _assign_request_id():
    incoming_request_id = (request.headers.get("X-Request-ID") or "").strip()
    g.request_id = incoming_request_id or uuid.uuid4().hex


@app.before_request
def _enforce_max_request_size():
    max_body_size = app.config.get("MAX_CONTENT_LENGTH")
    content_length = request.content_length
    if max_body_size and content_length and content_length > max_body_size:
        abort(413)


@app.after_request
def _log_response(response):
    request_id = getattr(g, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    app.logger.info(
        "request_completed method=%s path=%s status=%s remote_addr=%s",
        request.method,
        request.path,
        response.status_code,
        request.remote_addr or "-",
    )
    return response

@event.listens_for(Session, "after_commit")
def _touch_dashboard_version(_session):
    app.config["DASHBOARD_LAST_COMMIT_AT"] = datetime.utcnow().isoformat()

from app import routes, models
