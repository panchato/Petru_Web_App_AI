import os
import shutil
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def _default_app_data_root():
    app_data_root = os.environ.get("PETRU_APPDATA_DIR")
    if app_data_root:
        os.makedirs(app_data_root, exist_ok=True)
        return app_data_root

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        app_data_root = os.path.join(local_app_data, "Petru_Webapp")
    else:
        app_data_root = os.path.join(os.path.expanduser("~"), ".petru_webapp")

    os.makedirs(app_data_root, exist_ok=True)
    return app_data_root


def _int_from_env(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _default_database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # Keep local SQLite data outside the repo so branch operations do not remove it.
    app_data_root = _default_app_data_root()
    new_db_path = os.path.join(app_data_root, "database.db")
    legacy_db_path = os.path.join(basedir, "instance", "database.db")
    if not os.path.exists(new_db_path) and os.path.exists(legacy_db_path):
        shutil.copy2(legacy_db_path, new_db_path)

    return "sqlite:///" + new_db_path


def _default_upload_root():
    configured_root = os.environ.get("PETRU_UPLOADS_DIR")
    if configured_root:
        return os.path.abspath(configured_root)
    return os.path.join(_default_app_data_root(), "uploads")


class Config(object):
    SQLALCHEMY_DATABASE_URI = _default_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENVIRONMENT = (os.environ.get("FLASK_ENV") or "production").lower()
    IS_DEVELOPMENT = ENVIRONMENT in {"development", "dev", "local", "testing"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = not IS_DEVELOPMENT
    SESSION_COOKIE_SAMESITE = "Lax" if IS_DEVELOPMENT else "Strict"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    MAX_CONTENT_LENGTH = _int_from_env("MAX_CONTENT_LENGTH_BYTES", 16 * 1024 * 1024)
    MAX_UPLOAD_FILE_BYTES = _int_from_env("MAX_UPLOAD_FILE_BYTES", 8 * 1024 * 1024)
    DEFAULT_PAGE_SIZE = _int_from_env("DEFAULT_PAGE_SIZE", 10)
    MAX_PAGE_SIZE = _int_from_env("MAX_PAGE_SIZE", 200)
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = _int_from_env("CACHE_TIMEOUT_DASHBOARD", 60)
    WTF_CSRF_ENABLED = True
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    
    # SECURITY WARNING: Setup a proper SECRET_KEY in production!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'very_secret_key'
    
    UPLOAD_ROOT = _default_upload_root()
    UPLOAD_PATH_IMAGE = os.path.join(UPLOAD_ROOT, 'images')
    UPLOAD_PATH_PDF = os.path.join(UPLOAD_ROOT, 'pdf')
    PDF_CACHE_DIR = os.path.abspath(
        os.environ.get("PDF_CACHE_DIR", os.path.join(basedir, "static", "pdf_cache"))
    )
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
    VIRUS_SCAN_ENABLED = str(os.environ.get("VIRUS_SCAN_ENABLED", "0")).lower() in {"1", "true", "yes"}
    VIRUS_SCAN_COMMAND = os.environ.get("VIRUS_SCAN_COMMAND", "clamscan --no-summary")
    VIRUS_SCAN_TIMEOUT_SECONDS = _int_from_env("VIRUS_SCAN_TIMEOUT_SECONDS", 30)
