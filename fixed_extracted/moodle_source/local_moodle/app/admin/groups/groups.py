from flask import render_template, request

from .__blueprint__ import admin_groups_bp
from app import db
from app.models import Group


@admin_groups_bp.route('/edit_groups')
def edit_groups():
    groups = list(db.session.query(Group).all())
    return render_template("admin/edit_groups.html", groups=groups)


@admin_groups_bp.route('/add_group', methods=['POST'])
def add_group():
    data = request.json
    data['size'] = int(data['size'])
    existing_group = Group.query.filter_by(name=data['name']).first()
    if existing_group:
        existing_group.name = data['name']
        existing_group.size = data['size']
    else:
        group = Group(
            name=data['name'],
            size=data['size'],
        )
        db.session.add(group)
    db.session.commit()
    return {'success': True}


@admin_groups_bp.route('/remove_group', methods=['POST'])
def remove_group():
    data = request.json
    existing_group = Group.query.filter_by(name=data['name']).first()
    db.session.delete(existing_group)
    db.session.commit()
    return {'success': True}
