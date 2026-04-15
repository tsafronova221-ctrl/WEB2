import uuid


class Config:
    SECRET_KEY = '2893b6e6bdd540afaca7d18dbc62568e'
    SQLALCHEMY_DATABASE_URI = "sqlite:///../instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = False  # Отключено для HTTP (локальная разработка)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
