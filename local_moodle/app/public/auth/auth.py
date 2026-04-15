from flask import render_template, request, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, UserMixin

from .__blueprint__ import auth_bp
from app import login_manager
from app.security import hash_password


USERS = {
    "admin": hash_password("admin123"),
    "teacher": hash_password("teacher123"),
}


class SimpleUser(UserMixin):
    def __init__(self, username):
        self.id = username


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and verify_password(password, USERS[username]):
            user = SimpleUser(username)
            login_user(user)
            return redirect(url_for("admin.index"))

        return render_template("admin/login.html", error="Неверный логин или пароль")

    return render_template("admin/login.html")


def verify_password(plain, hashed):
    from app.security import hash_password
    return hash_password(plain) == hashed


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
