import hashlib
import secrets
from config import Config


def hash_password(p):
    """Hash password with salt using SHA256"""
    salt = Config.SECRET_KEY[:16]
    return hashlib.sha256((salt + p).encode()).hexdigest()


def verify_password(plain, hashed):
    return hash_password(plain) == hashed


def generate_watermark_hash(attempt):
    data = f"{Config.SECRET_KEY}|{attempt.id}|{attempt.student_id}|{attempt.lab_id if hasattr(attempt, 'lab_id') else attempt.protection_id}|{attempt.score}|{attempt.finished_at}"
    return hashlib.sha256(data.encode()).hexdigest()[:24]
