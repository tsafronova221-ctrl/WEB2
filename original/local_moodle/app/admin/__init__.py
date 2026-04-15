from flask import Blueprint, render_template

from .groups import admin_groups_bp
from .labs import admin_labs_bp

admin_bp = Blueprint('admin', __name__)
admin_bp.register_blueprint(admin_groups_bp)
admin_bp.register_blueprint(admin_labs_bp)


@admin_bp.route("/")
def index():
    return render_template("admin/index.html")
