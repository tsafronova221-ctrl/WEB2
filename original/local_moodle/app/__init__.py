# -*- coding: utf-8 -*-
import os

from flask import Flask, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

login_manager = LoginManager()
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__, instance_relative_config=True, 
                template_folder='templates', 
                static_folder='static')
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from .public.routes import public_bp
    from .public.auth import auth_bp
    from .admin import admin_bp

    @admin_bp.before_request
    def before_request():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route('/.well-known/appspecific/com.chrome.devtools.json')
    def workspace():
        return {
            'workspace': {
                'root': os.getcwd(),
                'uuid': '019b69dd-9888-7557-bd63-a3c579e74250',
            }
        }



    return app