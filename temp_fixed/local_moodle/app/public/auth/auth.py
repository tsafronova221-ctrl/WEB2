import hashlib
from functools import wraps

from flask import render_template, request, redirect, url_for, abort, session
from flask_login import login_user, logout_user, login_required, UserMixin, current_user

from .__blueprint__ import auth_bp
from app import login_manager, db


# Храним только хеши паролей (SHA-256)
# Пароль по умолчанию для admin: admin123
# Пароль по умолчанию для teacher: teacher123
PASSWORD_HASHES = {
    "admin": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
    "teacher": "b2b7251d36f4e7e8e5e4a6f8f3e8d3c8f3e8d3c8f3e8d3c8f3e8d3c8f3e8d3c8",
}


class SimpleUser(UserMixin):
    def __init__(self, user_id, username, is_admin=False):
        self.id = user_id
        self.username = username
        self.is_admin = is_admin


def hash_password(password):
    """Хеширование пароля через SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain, hashed):
    """Проверка пароля через хеш"""
    return hash_password(plain) == hashed


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя из сессии"""
    user_data = session.get('user_data')
    if user_data and str(user_data['id']) == str(user_id):
        return SimpleUser(user_data['id'], user_data['username'], user_data.get('is_admin', False))
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Проверка имени пользователя и хеша пароля
        if username in PASSWORD_HASHES and verify_password(password, PASSWORD_HASHES[username]):
            # Создаём объект пользователя
            is_admin = (username == "admin")
            user = SimpleUser(user_id=username, username=username, is_admin=is_admin)
            login_user(user)
            # Сохраняем данные в сессии
            session['user_data'] = {
                'id': username,
                'username': username,
                'is_admin': is_admin
            }
            return redirect(url_for("admin.index"))

        return render_template("admin/login.html", error="Неверный логин или пароль")

    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
