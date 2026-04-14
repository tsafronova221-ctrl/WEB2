from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, UserMixin
from functools import wraps

from .__blueprint__ import auth_bp
from app import login_manager


USERS = {
    "admin": "!!FaKe@@_L0l_m@y!!!!FaKe@@_L0l_m@y!!",
    "teacher": "!!FaKe@@_L0l_m@y!!!!FaKe@@_L0l_m@y!!",
}


@login_manager.user_loader
def load_user(username):
    if username in USERS:
        return SimpleUser(username)
    return None


class SimpleUser(UserMixin):
    def __init__(self, username):
        self.id = username


def admin_required(f):
    """Decorator для защиты админских маршрутов"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Ограничение количества попыток входа (простая защита от брутфорса)
        attempt_key = f'login_attempts_{request.remote_addr}'
        attempts = session.get(attempt_key, 0)
        
        if attempts >= 5:
            return render_template("admin/login.html", error="Слишком много неудачных попыток. Попробуйте позже.")

        if username in USERS and USERS[username] == password:
            user = SimpleUser(username)
            login_user(user)
            # Сброс счетчика попыток при успешном входе
            session.pop(attempt_key, None)
            return redirect(url_for("admin.index"))

        # Увеличиваем счетчик неудачных попыток
        session[attempt_key] = attempts + 1
        return render_template("admin/login.html", error="Неверный логин или пароль")

    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
