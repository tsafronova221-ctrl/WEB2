import os
import secrets


class Config:
    # SECRET_KEY должен генерироваться случайно и храниться в переменной окружения
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "sqlite:///instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Безопасные настройки сессий
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Установить True при использовании HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 час
