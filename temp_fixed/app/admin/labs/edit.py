from flask import render_template, request, Blueprint, Response, jsonify, abort
from .__blueprint__ import admin_labs_bp
from app import db
from app.models import Group, Lab, LabFile, Question, FileQuestionAnswer, LabPassword
import base64
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
import re
import secrets
import string

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')


def generate_password(length=10):
    """Генерация криптографически стойкого пароля"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_lab_name(name):
    """Валидация названия лабораторной работы"""
    if not name or not isinstance(name, str):
        return False, "Название не может быть пустым"
    
    name = name.strip()
    
    if len(name) < 3:
        return False, "Название должно содержать минимум 3 символа"
    
    if len(name) > 128:
        return False, "Название должно содержать максимум 128 символов"
    
    # Базовая санитизация
    name = re.sub(r'[<>\"\'&]', '', name)
    
    return True, name


def validate_description(description):
    """Валидация описания"""
    if not description:
        return True, ""
    
    if not isinstance(description, str):
        return False, "Описание должно быть строкой"
    
    if len(description) > 5000:
        return False, "Описание слишком длинное"
    
    # Санитизация HTML тегов
    description = re.sub(r'<script[^>]*>.*?</script>', '', description, flags=re.IGNORECASE | re.DOTALL)
    description = re.sub(r'<[^>]+>', '', description)
    
    return True, description


def validate_date(date_str):
    """Валидация даты"""
    if not date_str:
        return False, "Дата обязательна"
    
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = MSK.localize(dt).replace(tzinfo=None)
        return True, dt
    except (ValueError, TypeError):
        return False, "Некорректный формат даты"


def validate_base64_file(base64_data, max_size_mb=10):
    """Валидация и декодирование base64 файла"""
    if not base64_data or not isinstance(base64_data, str):
        return False, "Некорректные данные файла", None
    
    try:
        # Удаляем префикс data:...;base64, если есть
        b64_content = base64_data.split('base64,')[-1]
        
        # Проверяем размер до декодирования (примерно)
        if len(b64_content) > max_size_mb * 1024 * 1024 * 1.33:
            return False, f"Файл слишком большой (максимум {max_size_mb}MB)", None
        
        content = base64.b64decode(b64_content)
        
        # Проверяем размер после декодирования
        if len(content) > max_size_mb * 1024 * 1024:
            return False, f"Файл слишком большой (максимум {max_size_mb}MB)", None
        
        return True, "OK", content
    except Exception as e:
        return False, f"Ошибка декодирования файла: {str(e)}", None


def sanitize_filename(filename):
    """Очистка имени файла от опасных символов"""
    if not filename or not isinstance(filename, str):
        return False, "Некорректное имя файла", None
    
    filename = filename.strip()
    
    if len(filename) > 255:
        return False, "Имя файла слишком длинное", None
    
    # Разрешаем только безопасные символы
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    # Удаляем множественные точки
    filename = re.sub(r'\.+', '.', filename)
    
    # Убираем точку в начале
    filename = filename.lstrip('.')
    
    if not filename:
        return False, "Некорректное имя файла", None
    
    return True, filename, None


def ensure_lab_passwords(lab_id):
    """Создание паролей для лабораторной работы"""
    lab = Lab.query.get(lab_id)
    if not lab:
        return []

    # Если уже есть — не генерим заново
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
def delete_lab(lab_id):
    lab = Lab.query.get(lab_id)
    if not lab:
        return jsonify({"success": False, "error": "ЛР не найдена"}), 404

    # Каскадное удаление связанных данных
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
def update_lab(lab_id):
    # Проверка Content-Type
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Неверный формат данных'}), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Пустые данные'}), 400

    lab = Lab.query.get_or_404(lab_id)

    # Валидация и обновление основной информации
    valid, result = validate_lab_name(data.get('name'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    lab.title = result

    valid, result = validate_description(data.get('description'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    lab.description = result

    # Валидация дат
    valid, start_dt = validate_date(data.get('start_date'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    
    valid, deadline_dt = validate_date(data.get('deadline'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    
    # Проверка что дедлайн позже начала
    if deadline_dt <= start_dt:
        return jsonify({'success': False, 'error': 'Дедлайн должен быть позже даты начала'}), 400

    lab.start_at = start_dt
    lab.deadline_at = deadline_dt
    
    # Валидация булевых значений
    lab.is_test = bool(data.get('is_test', False))
    
    # Валидация числовых значений
    try:
        lab.questions_count = max(0, min(1000, int(data.get('questions_count', 0))))
        lab.test_duration = max(0, min(1440, int(data.get('test_duration', 0))))  # Максимум 24 часа
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Некорректные числовые значения'}), 400

    # Обновление групп
    try:
        group_ids = [int(g) for g in data.get('groups', [])]
        lab.groups = Group.query.filter(Group.id.in_(group_ids)).all()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Некорректные ID групп'}), 400

    # Обновление файлов с валидацией
    existing_files = {f.id: f for f in LabFile.query.filter_by(lab_id=lab_id).all()}
    new_files = data.get('files', [])
    
    if not isinstance(new_files, list):
        return jsonify({'success': False, 'error': 'Некорректный формат файлов'}), 400

    files_dir = os.path.join("instance", "labs", str(lab_id))
    os.makedirs(files_dir, exist_ok=True)

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

    # 2. Заменяем файлы с валидацией
    for f in new_files:
        if f.get("action") == "replace":
            file_id = f.get("id")
            if file_id and file_id in existing_files:
                # Валидация имени файла
                valid, name, _ = sanitize_filename(f.get('name'))
                if not valid:
                    return jsonify({'success': False, 'error': f'Некорректное имя файла: {name}'}), 400
                
                # Валидация base64 содержимого
                valid, msg, content = validate_base64_file(f.get('base64'))
                if not valid:
                    return jsonify({'success': False, 'error': msg}), 400

                # Удаляем старый файл
                try:
                    os.remove(existing_files[file_id].file_path)
                except OSError:
                    pass

                # Сохраняем новый
                file_path = os.path.join(files_dir, name)
                with open(file_path, "wb") as fp:
                    fp.write(content)

                existing_files[file_id].file_path = file_path

    # 3. Добавляем новые файлы с валидацией
    for f in new_files:
        if f.get("action") == "add":
            # Валидация имени файла
            valid, name, _ = sanitize_filename(f.get('name'))
            if not valid:
                return jsonify({'success': False, 'error': f'Некорректное имя файла: {name}'}), 400
            
            # Валидация base64 содержимого
            valid, msg, content = validate_base64_file(f.get('base64'))
            if not valid:
                return jsonify({'success': False, 'error': msg}), 400

            file_path = os.path.join(files_dir, name)
            with open(file_path, "wb") as fp:
                fp.write(content)

            lf = LabFile(lab_id=lab.id, file_path=file_path)
            db.session.add(lf)
            db.session.flush()
            existing_files[lf.id] = lf

    # Обновление вопросов с валидацией
    Question.query.filter_by(lab_id=lab_id).delete()
    db.session.flush()

    question_objs = []
    questions_data = data.get('questions', [])
    
    if not isinstance(questions_data, list):
        return jsonify({'success': False, 'error': 'Некорректный формат вопросов'}), 400
    
    for q in questions_data:
        if not isinstance(q, dict):
            continue
        
        q_text = q.get('text', '').strip()
        if not q_text:
            continue
        
        # Санитизация текста вопроса
        q_text = re.sub(r'<script[^>]*>.*?</script>', '', q_text, flags=re.IGNORECASE | re.DOTALL)
        q_text = re.sub(r'<[^>]+>', '', q_text)
        
        if len(q_text) > 512:
            q_text = q_text[:512]
        
        q_obj = Question(lab_id=lab.id, text=q_text)
        db.session.add(q_obj)
        question_objs.append(q_obj)

    db.session.flush()

    # Обновление ответов с валидацией
    db.session.query(FileQuestionAnswer).filter(
        FileQuestionAnswer.lab_file_id.in_(
            db.session.query(LabFile.id).filter(LabFile.lab_id == lab_id)
        )
    ).delete(synchronize_session=False)
    db.session.flush()

    for q, q_obj in zip(questions_data, question_objs):
        for ans in q.get('answers', []):
            try:
                file_id = int(ans.get('file_id'))
                correct_answer = str(ans.get('correct_answer', '')).strip()
                
                # Ограничение длины ответа
                if len(correct_answer) > 256:
                    correct_answer = correct_answer[:256]
                
                # Санитизация ответа
                correct_answer = re.sub(r'<script[^>]*>.*?</script>', '', correct_answer, flags=re.IGNORECASE | re.DOTALL)
                correct_answer = re.sub(r'<[^>]+>', '', correct_answer)

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
        ET.SubElement(q, "responseformat").text = "editorfilepicker"
        ET.SubElement(q, "responserequired").text = "1"
        ET.SubElement(q, "responsefieldlines").text = "10"

        ET.SubElement(q, "minwordlimit").text = ""
        ET.SubElement(q, "maxwordlimit").text = ""

        # требуем хотя бы один файл-вложение
        ET.SubElement(q, "attachments").text = "1"
        ET.SubElement(q, "attachmentsrequired").text = "1"
        ET.SubElement(q, "maxbytes").text = "0"

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
