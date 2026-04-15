from flask import render_template, request, jsonify
import re

from .__blueprint__ import admin_groups_bp
from app import db
from app.models import Group


def validate_group_name(name):
    """Валидация имени группы"""
    if not name or not isinstance(name, str):
        return False, "Имя группы не может быть пустым"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Имя группы должно содержать минимум 2 символа"
    
    if len(name) > 64:
        return False, "Имя группы должно содержать максимум 64 символа"
    
    # Разрешаем только буквы, цифры, дефис и пробелы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-]+$', name):
        return False, "Имя группы содержит недопустимые символы"
    
    return True, name


def validate_group_size(size):
    """Валидация размера группы"""
    try:
        size = int(size)
        if size < 0:
            return False, "Размер группы не может быть отрицательным"
        if size > 10000:
            return False, "Размер группы слишком большой"
        return True, size
    except (ValueError, TypeError):
        return False, "Некорректный размер группы"


@admin_groups_bp.route('/edit_groups')
def edit_groups():
    groups = list(db.session.query(Group).all())
    return render_template("admin/edit_groups.html", groups=groups)


@admin_groups_bp.route('/add_group', methods=['POST'])
def add_group():
    # Проверка Content-Type
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Неверный формат данных'}), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Пустые данные'}), 400
    
    # Валидация имени группы
    valid, result = validate_group_name(data.get('name'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    
    group_name = result
    
    # Валидация размера группы
    valid, result = validate_group_size(data.get('size'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    
    group_size = result
    
    existing_group = Group.query.filter_by(name=group_name).first()
    if existing_group:
        existing_group.name = group_name
        existing_group.size = group_size
    else:
        group = Group(
            name=group_name,
            size=group_size,
        )
        db.session.add(group)
    
    db.session.commit()
    return jsonify({'success': True})


@admin_groups_bp.route('/remove_group', methods=['POST'])
def remove_group():
    # Проверка Content-Type
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Неверный формат данных'}), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Пустые данные'}), 400
    
    # Валидация имени группы
    valid, result = validate_group_name(data.get('name'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    
    group_name = result
    
    existing_group = Group.query.filter_by(name=group_name).first()
    if not existing_group:
        return jsonify({'success': False, 'error': 'Группа не найдена'}), 404
    
    db.session.delete(existing_group)
    db.session.commit()
    return jsonify({'success': True})
