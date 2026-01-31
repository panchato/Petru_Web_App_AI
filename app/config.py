import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'very_secret_key'
    UPLOAD_PATH_IMAGE = os.path.join(basedir, 'static', 'images')
    UPLOAD_PATH_PDF = os.path.join(basedir, 'static', 'pdf')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}