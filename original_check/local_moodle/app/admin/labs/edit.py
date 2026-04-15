from flask import render_template, request, Blueprint, Response
from .__blueprint__ import admin_labs_bp
from app import db
from app.models import Group, Lab, LabFile, Question, FileQuestionAnswer, LabPassword
import base64
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')


import secrets
import string


def generate_password(length=10):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


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
def delete_lab(lab_id):
    lab = Lab.query.get(lab_id)
    if not lab:
        return {"success": False, "error": "ЛР не найдена"}

    FileQuestionAnswer.query.filter(FileQuestionAnswer.question_id.in_(
        db.session.query(Question.id).filter_by(lab_id=lab_id)
    )).delete(synchronize_session=False)

    Question.query.filter_by(lab_id=lab_id).delete()
    LabFile.query.filter_by(lab_id=lab_id).delete()
    LabPassword.query.filter_by(lab_id=lab_id).delete()
    db.session.commit()
    db.session.delete(lab)
    db.session.commit()

    return {"success": True}


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
    data = request.json

    lab = Lab.query.get_or_404(lab_id)

    # Обновляем основную информацию
    # Парсим даты с учетом часового пояса Москвы
    start_dt = datetime.fromisoformat(data['start_date'])
    deadline_dt = datetime.fromisoformat(data['deadline'])
    
    # Если даты без timezone info, считаем что это время по Москве и сохраняем без tzinfo
    if start_dt.tzinfo is None:
        start_dt = MSK.localize(start_dt).replace(tzinfo=None)  # Сохраняем как naive datetime
    if deadline_dt.tzinfo is None:
        deadline_dt = MSK.localize(deadline_dt).replace(tzinfo=None)  # Сохраняем как naive datetime
    
    lab.title = data['name']
    lab.description = data['description']
    lab.start_at = start_dt
    lab.deadline_at = deadline_dt
    lab.is_test = data.get('is_test', False)
    lab.questions_count = int(data.get('questions_count', 0))
    lab.test_duration = int(data.get('test_duration', 0))

    # Обновляем группы
    group_ids = [int(g) for g in data['groups']]
    lab.groups = Group.query.filter(Group.id.in_(group_ids)).all()

    # Обновляем файлы
    existing_files = {f.id: f for f in LabFile.query.filter_by(lab_id=lab_id).all()}
    new_files = data['files']  # [{id?, name, base64?, action}]

    files_dir = os.path.join("instance", "labs", str(lab.id))
    os.makedirs(files_dir, exist_ok=True)

    # 1. Удаляем файлы
    for f in new_files:
        if f.get("action") == "delete":
            file_id = f["id"]
            if file_id in existing_files:
                try:
                    os.remove(existing_files[file_id].file_path)
                except:
                    pass
                db.session.delete(existing_files[file_id])
                existing_files.pop(file_id)

    # 2. Заменяем файлы
    for f in new_files:
        if f.get("action") == "replace":
            file_id = f["id"]
            if file_id in existing_files:
                # удаляем старый файл
                try:
                    os.remove(existing_files[file_id].file_path)
                except:
                    pass

                # сохраняем новый
                name = f['name']
                b64 = f['base64'].split('base64,')[-1]
                content = base64.b64decode(b64)

                file_path = os.path.join(files_dir, name)
                with open(file_path, "wb") as fp:
                    fp.write(content)

                existing_files[file_id].file_path = file_path

    # 3. Добавляем новые файлы
    for f in new_files:
        if f.get("action") == "add":
            name = f['name']
            b64 = f['base64'].split('base64,')[-1]
            content = base64.b64decode(b64)

            file_path = os.path.join(files_dir, name)
            with open(file_path, "wb") as fp:
                fp.write(content)

            lf = LabFile(lab_id=lab.id, file_path=file_path)
            db.session.add(lf)
            db.session.flush()
            existing_files[lf.id] = lf

    # Обновляем вопросы
    Question.query.filter_by(lab_id=lab_id).delete()
    db.session.flush()

    question_objs = []
    for q in data['questions']:
        q_obj = Question(lab_id=lab.id, text=q['text'])
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
            file_id = int(ans['file_id'])
            correct_answer = ans['correct_answer']

            fqa = FileQuestionAnswer(
                lab_file_id=file_id,
                question_id=q_obj.id,
                correct_answer=correct_answer
            )
            db.session.add(fqa)

    db.session.commit()
    return {"success": True}


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

