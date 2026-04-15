import uuid
import os

class Config:
    # Use environment variable for SECRET_KEY in production, fallback to secure random value
    SECRET_KEY = os.environ.get('SECRET_KEY', uuid.uuid4().hex)
    SQLALCHEMY_DATABASE_URI = "sqlite:///../instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Security settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session timeout
