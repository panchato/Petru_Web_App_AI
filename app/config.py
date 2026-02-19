import os
import shutil
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def _default_database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # Keep local SQLite data outside the repo so branch operations do not remove it.
    app_data_root = os.environ.get("PETRU_APPDATA_DIR")
    if not app_data_root:
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            app_data_root = os.path.join(local_app_data, "Petru_Webapp")
        else:
            app_data_root = os.path.join(os.path.expanduser("~"), ".petru_webapp")

    os.makedirs(app_data_root, exist_ok=True)
    new_db_path = os.path.join(app_data_root, "database.db")
    legacy_db_path = os.path.join(basedir, "instance", "database.db")
    if not os.path.exists(new_db_path) and os.path.exists(legacy_db_path):
        shutil.copy2(legacy_db_path, new_db_path)

    return "sqlite:///" + new_db_path


class Config(object):
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    
    # SECURITY WARNING: Setup a proper SECRET_KEY in production!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'very_secret_key'
    
    UPLOAD_PATH_IMAGE = os.path.join(basedir, 'static', 'images')
    UPLOAD_PATH_PDF = os.path.join(basedir, 'static', 'pdf')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
