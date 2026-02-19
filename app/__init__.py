from flask import Flask
from app.config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.orm import Session
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
app.config["DASHBOARD_LAST_COMMIT_AT"] = datetime.utcnow().isoformat()

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = "login"
migrate = Migrate(app, db)

@event.listens_for(Session, "after_commit")
def _touch_dashboard_version(_session):
    app.config["DASHBOARD_LAST_COMMIT_AT"] = datetime.utcnow().isoformat()

from app import routes, models
