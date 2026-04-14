import hashlib
import secrets
from config import Config


def hash_password(p):
    # Используем bcrypt-like хеширование с солью для большей безопасности
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', p.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_obj.hex()}"


def verify_password(plain, hashed):
    try:
        salt, hash_value = hashed.split(':')
        hash_obj = hashlib.pbkdf2_hmac('sha256', plain.encode(), salt.encode(), 100000)
        return hash_obj.hex() == hash_value
    except (ValueError, AttributeError):
        # Для обратной совместимости со старыми хешами (без соли)
        return hash_password(plain).split(':')[1] == hashed or hashlib.sha256(plain.encode()).hexdigest() == hashed


def generate_watermark_hash(attempt):
    data = f"{Config.SECRET_KEY}|{attempt.id}|{attempt.student_id}|{attempt.lab_id if hasattr(attempt, 'lab_id') else attempt.protection_id}|{attempt.score}|{attempt.finished_at}"
    return hashlib.sha256(data.encode()).hexdigest()[:24]
