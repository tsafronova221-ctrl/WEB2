import hashlib
from config import Config


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


def verify_password(plain, hashed):
    return hash_password(plain) == hashed


def generate_watermark_hash(attempt):
    data = f"{Config.SECRET_KEY}|{attempt.id}|{attempt.student_id}|{attempt.lab_id if hasattr(attempt, 'lab_id') else attempt.protection_id}|{attempt.score}|{attempt.finished_at}"
    return hashlib.sha256(data.encode()).hexdigest()[:24]
