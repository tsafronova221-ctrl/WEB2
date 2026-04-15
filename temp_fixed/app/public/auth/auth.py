from flask import render_template, request, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, UserMixin
import os
import hashlib

from .__blueprint__ import auth_bp
from app import login_manager


# Хеши паролей для пользователей (в production хранить в БД!)
# Пароли по умолчанию: admin/admin123, teacher/teacher123
USERS = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "teacher": hashlib.sha256("teacher123".encode()).hexdigest(),
}


@login_manager.user_loader
def load_user(username):
    if username in USERS:
        return SimpleUser(username)
    return None


class SimpleUser(UserMixin):
    def __init__(self, username):
        self.id = username


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Если уже авторизован - перенаправляем на главную админки
    if session.get('user_id'):
        return redirect(url_for("admin.index"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Валидация входных данных
        if not username or not password:
            return render_template("admin/login.html", error="Введите логин и пароль")
        
        if len(username) > 50:
            return render_template("admin/login.html", error="Слишком длинный логин")
        
        if len(password) > 100:
            return render_template("admin/login.html", error="Слишком длинный пароль")

        # Проверка пароля с использованием хеша
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if username in USERS and USERS[username] == password_hash:
            user = SimpleUser(username)
            login_user(user)
            session['user_id'] = username
            session.permanent = True  # Устанавливаем постоянную сессию
            return redirect(url_for("admin.index"))

        return render_template("admin/login.html", error="Неверный логин или пароль")

    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop('user_id', None)
    return redirect(url_for("auth.login"))
