from flask import render_template, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, UserMixin

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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and USERS[username] == password:
            user = SimpleUser(username)
            login_user(user)
            return redirect(url_for("admin.index"))

        return render_template("admin/login.html", error="Неверный логин или пароль")

    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
