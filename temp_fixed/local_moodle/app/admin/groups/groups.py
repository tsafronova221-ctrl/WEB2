from flask import render_template, request, jsonify, abort
from functools import wraps

from .__blueprint__ import admin_groups_bp
from app import db
from app.models import Group


def require_json(f):
    """Decorator для проверки Content-Type и валидации JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            abort(400, "Content-Type must be application/json")
        return f(*args, **kwargs)
    return decorated_function


@admin_groups_bp.route('/edit_groups')
def edit_groups():
    groups = list(db.session.query(Group).all())
    return render_template("admin/edit_groups.html", groups=groups)


@admin_groups_bp.route('/add_group', methods=['POST'])
@require_json
def add_group():
    data = request.get_json()
    
    # Валидация входных данных
    if not data or 'name' not in data or 'size' not in data:
        abort(400, "Missing required fields: name, size")
    
    # Проверка типа и диапазона значений
    try:
        size = int(data['size'])
        if size <= 0 or size > 1000:
            abort(400, "Size must be between 1 and 1000")
    except (ValueError, TypeError):
        abort(400, "Invalid size value")
    
    # Санитизация имени группы
    name = str(data['name']).strip()
    if not name or len(name) > 64:
        abort(400, "Invalid group name")
    
    existing_group = Group.query.filter_by(name=name).first()
    if existing_group:
        existing_group.name = name
        existing_group.size = size
    else:
        group = Group(
            name=name,
            size=size,
        )
        db.session.add(group)
    db.session.commit()
    return jsonify({'success': True})


@admin_groups_bp.route('/remove_group', methods=['POST'])
@require_json
def remove_group():
    data = request.get_json()
    
    # Валидация входных данных
    if not data or 'name' not in data:
        abort(400, "Missing required field: name")
    
    name = str(data['name']).strip()
    existing_group = Group.query.filter_by(name=name).first()
    
    if not existing_group:
        abort(404, "Group not found")
    
    db.session.delete(existing_group)
    db.session.commit()
    return jsonify({'success': True})
