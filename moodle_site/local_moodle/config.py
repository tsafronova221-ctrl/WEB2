import uuid
import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or uuid.uuid4().hex
    SQLALCHEMY_DATABASE_URI = "sqlite:///../instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Отключаем истечение CSRF токенов по времени
