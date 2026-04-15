import os
import uuid


class Config:
    # SECRET_KEY берётся из переменной окружения или генерируется случайно
    # В production обязательно установите SECRET_KEY через环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY') or uuid.uuid4().hex
    
    # Безопасные настройки сессий
    SESSION_COOKIE_HTTPONLY = True  # Запрет доступа к cookie через JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Защита от CSRF
    SESSION_COOKIE_SECURE = False  # Установить True в production при использовании HTTPS
    
    # Время жизни сессии (30 минут бездействия)
    PERMANENT_SESSION_LIFETIME = 1800
    
    SQLALCHEMY_DATABASE_URI = "sqlite:///../instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Максимальный размер загружаемого файла (10 MB)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    
    # Разрешённые расширения для загрузки
    ALLOWED_EXTENSIONS = {'vhd', 'vhdx', 'iso', 'img', 'bin', 'zip', 'rar', '7z'}
