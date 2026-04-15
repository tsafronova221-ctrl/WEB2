from flask import render_template, request, Blueprint, Response, jsonify, abort
from .__blueprint__ import admin_labs_bp
from app import db
from app.models import Group, Lab, LabFile, Question, FileQuestionAnswer, LabPassword
import base64
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from functools import wraps
import re

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')


import secrets
import string


def generate_password(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def require_json(f):
    """Decorator для проверки Content-Type и валидации JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            abort(400, "Content-Type must be application/json")
        return f(*args, **kwargs)
    return decorated_function


def sanitize_filename(filename):
    """Санитизация имени файла"""
    # Разрешаем только буквы, цифры, точки, дефисы и подчёркивания
    filename = re.sub(r'[^\w\.\-]', '', filename)
    # Ограничиваем длину
    return filename[:255]


def validate_base64(b64_string):
    """Проверка корректности base64"""
    try:
        # Проверяем формат
        if ',' in b64_string:
            b64_data = b64_string.split('base64,')[-1]
        else:
            b64_data = b64_string
        
        # Декодируем для проверки
        base64.b64decode(b64_data)
        return True
    except Exception:
        return False


def ensure_lab_passwords(lab_id):
    lab = Lab.query.get(lab_id)
    if not lab:
        return []

    # уже есть — не генерим заново
    if lab.passwords:
        return lab.passwords

    passwords = []
    for f in LabFile.query.filter_by(lab_id=lab_id):
        pwd = LabPassword(
            lab_id=lab.id,
            file_id=f.id,
            password=generate_password(10),
        )
        db.session.add(pwd)
        passwords.append(pwd)

    db.session.commit()
    return passwords


@admin_labs_bp.route("/list")
def list_labs():
    groups = Group.query.all()
    labs = Lab.query.order_by(Lab.start_at.desc()).all()
    return render_template("admin/labs_list.html", labs=labs, groups=groups)


@admin_labs_bp.route("/delete/<int:lab_id>", methods=["POST"])
@require_json
def delete_lab(lab_id):
    lab = Lab.query.get(lab_id)
    if not lab:
        return jsonify({"success": False, "error": "ЛР не найдена"}), 404

    FileQuestionAnswer.query.filter(FileQuestionAnswer.question_id.in_(
        db.session.query(Question.id).filter_by(lab_id=lab_id)
    )).delete(synchronize_session=False)

    Question.query.filter_by(lab_id=lab_id).delete()
    LabFile.query.filter_by(lab_id=lab_id).delete()
    LabPassword.query.filter_by(lab_id=lab_id).delete()
    db.session.commit()
    db.session.delete(lab)
    db.session.commit()

    return jsonify({"success": True})


@admin_labs_bp.route("/edit_lab/<int:lab_id>")
def edit_lab(lab_id):
    lab = Lab.query.get_or_404(lab_id)

    files = []
    for f in LabFile.query.filter_by(lab_id=lab_id).all():
        files.append({
            "id": f.id,
            "name": os.path.basename(f.file_path)
        })
    questions = Question.query.filter_by(lab_id=lab_id).all()

    # Загружаем ответы по файлам
    answers = FileQuestionAnswer.query.join(LabFile).filter(LabFile.lab_id == lab_id).all()

    # Преобразуем в удобную структуру:
    # answers_map[question_id][file_id] = "ответ"
    answers_map = {}
    for ans in answers:
        answers_map.setdefault(ans.question_id, {})[ans.lab_file_id] = ans.correct_answer

    groups = Group.query.all()

    return render_template(
        "admin/edit_lab.html",
        lab=lab,
        files=files,
        questions=questions,
        answers=answers_map,
        groups=groups
    )


@admin_labs_bp.route("/edit_lab/<int:lab_id>", methods=["POST"])
@require_json
def update_lab(lab_id):
    data = request.get_json()
    
    # Валидация обязательных полей
    required_fields = ['name', 'start_date', 'deadline', 'description', 'groups', 'files', 'questions']
    for field in required_fields:
        if field not in data:
            abort(400, f"Missing required field: {field}")

    lab = Lab.query.get_or_404(lab_id)

    # Валидация и парсинг дат
    try:
        start_dt = datetime.fromisoformat(data['start_date'])
        deadline_dt = datetime.fromisoformat(data['deadline'])
        
        # Если даты без timezone info, считаем что это время по Москве
        if start_dt.tzinfo is None:
            start_dt = MSK.localize(start_dt).replace(tzinfo=None)
        if deadline_dt.tzinfo is None:
            deadline_dt = MSK.localize(deadline_dt).replace(tzinfo=None)
        
        # Проверка: дедлайн должен быть после начала
        if deadline_dt <= start_dt:
            abort(400, "Deadline must be after start date")
    except (ValueError, TypeError) as e:
        abort(400, f"Invalid date format: {str(e)}")
    
    # Валидация названия
    lab.title = str(data['name']).strip()[:128]
    if not lab.title:
        abort(400, "Lab title cannot be empty")
    
    # Валидация описания
    lab.description = str(data['description']).strip()[:10000]
    
    lab.start_at = start_dt
    lab.deadline_at = deadline_dt
    lab.is_test = bool(data.get('is_test', False))
    lab.questions_count = max(0, min(int(data.get('questions_count', 0)), 100))
    lab.test_duration = max(0, min(int(data.get('test_duration', 0)), 1440))  # макс 24 часа

    # Обновляем группы с валидацией
    try:
        group_ids = [int(g) for g in data['groups']]
        lab.groups = Group.query.filter(Group.id.in_(group_ids)).all()
    except (ValueError, TypeError):
        abort(400, "Invalid group IDs")

    # Валидация файлов
    files_dir = os.path.join("instance", "labs", str(lab_id))
    os.makedirs(files_dir, exist_ok=True)
    
    # Проверка на максимальное количество файлов
    if len(data['files']) > 50:
        abort(400, "Too many files (max 50)")
    
    # Максимальный размер файла (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Обновляем файлы
    existing_files = {f.id: f for f in LabFile.query.filter_by(lab_id=lab_id).all()}
    new_files = data['files']

    # 1. Удаляем файлы
    for f in new_files:
        if f.get("action") == "delete":
            file_id = f.get("id")
            if file_id and file_id in existing_files:
                try:
                    os.remove(existing_files[file_id].file_path)
                except OSError:
                    pass
                db.session.delete(existing_files[file_id])
                existing_files.pop(file_id)

    # 2. Заменяем файлы
    for f in new_files:
        if f.get("action") == "replace":
            file_id = f.get("id")
            if file_id and file_id in existing_files:
                # Проверяем наличие base64
                if 'base64' not in f or 'name' not in f:
                    abort(400, "Missing base64 or name for file replacement")
                
                # Валидация base64
                if not validate_base64(f['base64']):
                    abort(400, "Invalid base64 encoding")
                
                # удаляем старый файл
                try:
                    os.remove(existing_files[file_id].file_path)
                except OSError:
                    pass

                # сохраняем новый
                name = sanitize_filename(f['name'])
                if not name:
                    abort(400, "Invalid filename")
                
                b64 = f['base64'].split('base64,')[-1]
                content = base64.b64decode(b64)
                
                # Проверка размера
                if len(content) > MAX_FILE_SIZE:
                    abort(400, "File too large (max 10MB)")

                file_path = os.path.join(files_dir, name)
                with open(file_path, "wb") as fp:
                    fp.write(content)

                existing_files[file_id].file_path = file_path

    # 3. Добавляем новые файлы
    for f in new_files:
        if f.get("action") == "add":
            if 'base64' not in f or 'name' not in f:
                abort(400, "Missing base64 or name for new file")
            
            # Валидация base64
            if not validate_base64(f['base64']):
                abort(400, "Invalid base64 encoding")
            
            name = sanitize_filename(f['name'])
            if not name:
                abort(400, "Invalid filename")
            
            b64 = f['base64'].split('base64,')[-1]
            content = base64.b64decode(b64)
            
            # Проверка размера
            if len(content) > MAX_FILE_SIZE:
                abort(400, "File too large (max 10MB)")

            file_path = os.path.join(files_dir, name)
            with open(file_path, "wb") as fp:
                fp.write(content)

            lf = LabFile(lab_id=lab.id, file_path=file_path)
            db.session.add(lf)
            db.session.flush()
            existing_files[lf.id] = lf

    # Обновляем вопросы с валидацией
    Question.query.filter_by(lab_id=lab_id).delete()
    db.session.flush()

    # Проверка на максимальное количество вопросов
    if len(data['questions']) > 200:
        abort(400, "Too many questions (max 200)")

    question_objs = []
    for q in data['questions']:
        if 'text' not in q:
            abort(400, "Question text is required")
        
        q_obj = Question(lab_id=lab.id, text=str(q['text']).strip()[:512])
        db.session.add(q_obj)
        question_objs.append(q_obj)

    db.session.flush()

    # Обновляем ответы
    db.session.query(FileQuestionAnswer).filter(
        FileQuestionAnswer.lab_file_id.in_(
            db.session.query(LabFile.id).filter(LabFile.lab_id == lab_id)
        )
    ).delete(synchronize_session=False)
    db.session.flush()

    for q, q_obj in zip(data['questions'], question_objs):
        for ans in q.get('answers', []):
            if 'file_id' not in ans or 'correct_answer' not in ans:
                continue
            
            try:
                file_id = int(ans['file_id'])
                correct_answer = str(ans['correct_answer']).strip()[:256]

                fqa = FileQuestionAnswer(
                    lab_file_id=file_id,
                    question_id=q_obj.id,
                    correct_answer=correct_answer
                )
                db.session.add(fqa)
            except (ValueError, TypeError):
                continue

    db.session.commit()
    return jsonify({"success": True})


@admin_labs_bp.route("/<int:lab_id>/export_passwords_xml")
def export_passwords_xml(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    passwords = ensure_lab_passwords(lab_id)

    quiz = ET.Element("quiz")

    # категория
    category = ET.SubElement(quiz, "question", type="category")
    cattext = ET.SubElement(category, "category")
    cattext_text = ET.SubElement(cattext, "text")
    cattext_text.text = f"$course$/ЛР/{lab.title.replace(' ', '_')}"

    for idx, lp in enumerate(passwords, start=1):
        q = ET.SubElement(quiz, "question", type="essay")

        name = ET.SubElement(q, "name")
        name_text = ET.SubElement(name, "text")
        name_text.text = f"вариант {idx}"

        # <questiontext format="html"><text>...</text></questiontext>
        questiontext = ET.SubElement(q, "questiontext", format="html")
        qt_text = ET.SubElement(questiontext, "text")
        qt_text.text = (
            f"<p>Пароль для доступа к варианту №{idx}: "
            f"<strong>{lp.password}</strong></p>"
            f"<p>Загрузите изображение с результатом в виде файла.</p>"
        )

        # <generalfeedback format="html"><text></text></generalfeedback>
        gf = ET.SubElement(q, "generalfeedback", format="html")
        ET.SubElement(gf, "text").text = ""

        ET.SubElement(q, "defaultgrade").text = "1"
        ET.SubElement(q, "penalty").text = "0"
        ET.SubElement(q, "hidden").text = "0"

        # обязательные для Moodle поля
        ET.SubElement(q, "idnumber").text = ""

        # формат ответа: редактор + возможность прикрепить файл
        # (можно заменить на "noinline", если хочешь только файлы без текста)
        ET.SubElement(q, "responseformat").text = "editorfilepicker"
        ET.SubElement(q, "responserequired").text = "1"
        ET.SubElement(q, "responsefieldlines").text = "10"

        ET.SubElement(q, "minwordlimit").text = ""
        ET.SubElement(q, "maxwordlimit").text = ""

        # требуем хотя бы один файл-вложение
        ET.SubElement(q, "attachments").text = "1"
        ET.SubElement(q, "attachmentsrequired").text = "1"
        ET.SubElement(q, "maxbytes").text = "0"

        # можно оставить пустым (как в твоём примере), Moodle всё равно позволит картинки
        ET.SubElement(q, "filetypeslist").text = ""

        # <graderinfo format="html"><text></text></graderinfo>
        gi = ET.SubElement(q, "graderinfo", format="html")
        ET.SubElement(gi, "text").text = ""

        # <responsetemplate format="html"><text></text></responsetemplate>
        rt = ET.SubElement(q, "responsetemplate", format="html")
        ET.SubElement(rt, "text").text = ""

    xml_bytes = ET.tostring(quiz, encoding="utf-8", xml_declaration=True)

    filename = f"lab_{lab.id}_passwords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    return Response(
        xml_bytes,
        mimetype="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

