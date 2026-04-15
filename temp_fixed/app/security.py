import hashlib
import hmac
from config import Config


def hash_password(p):
    """Хеширование пароля с использованием SHA-256"""
    return hashlib.sha256(p.encode()).hexdigest()


def verify_password(plain, hashed):
    """Проверка пароля путём сравнения хешей"""
    return hmac.compare_digest(hash_password(plain), hashed)


def generate_watermark_hash(attempt):
    """Генерация хеша водяного знака для защиты результатов"""
    data = f"{Config.SECRET_KEY}|{attempt.id}|{attempt.student_id}|{attempt.lab_id if hasattr(attempt, 'lab_id') else attempt.protection_id}|{attempt.score}|{attempt.finished_at}"
    return hashlib.sha256(data.encode()).hexdigest()[:24]


def sanitize_filename(filename):
    """Очистка имени файла от опасных символов"""
    import re
    # Разрешаем только буквы, цифры, дефис, подчёркивание и точку
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    # Удаляем множественные точки
    filename = re.sub(r'\.+', '.', filename)
    # Ограничиваем длину
    return filename[:255]
