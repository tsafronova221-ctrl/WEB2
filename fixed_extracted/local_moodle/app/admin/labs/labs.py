from flask import render_template, request
from .__blueprint__ import admin_labs_bp
from app import db
from app.models import Group, Lab, LabFile, Question, FileQuestionAnswer
import base64
import os
from datetime import datetime
import pytz

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')


@admin_labs_bp.route("/create_labs")
def create_labs():
    groups = Group.query.all()
    return render_template("admin/edit_labs.html", groups=groups)


@admin_labs_bp.route("/create_lab", methods=["POST"])
def create_lab():
    data = request.json

    lab_name = data['name']
    deadline = data['deadline']          # строка, можешь потом привести к datetime
    start_date = data['start_date']
    description = data['description']
    group_ids = [int(g) for g in data['groups']]
    files = data['files']                # [{ name, base64 }]
    questions = data['questions']        # [{ number, text, answers: [{file_index, correct_answer}] }]
    is_test = data.get('is_test', False)
    questions_count = int(data.get('questions_count', 0))

    # 1. создаём ЛР
    # Парсим даты с учетом часового пояса Москвы
    start_dt = datetime.fromisoformat(start_date)
    deadline_dt = datetime.fromisoformat(deadline)
    
    # Если даты без timezone info, считаем что это время по Москве и сохраняем без tzinfo
    if start_dt.tzinfo is None:
        start_dt = MSK.localize(start_dt).replace(tzinfo=None)  # Сохраняем как naive datetime
    if deadline_dt.tzinfo is None:
        deadline_dt = MSK.localize(deadline_dt).replace(tzinfo=None)  # Сохраняем как naive datetime
    
    lab = Lab(
        title=lab_name,
        code=f"LAB-{int(datetime.now(MSK).timestamp())}",
        description=description,
        start_at=start_dt,
        deadline_at=deadline_dt,
        is_test=is_test,  # Сохраняем тип
        questions_count=questions_count,  # Сохраняем кол-во вопросов
        test_duration=int(data.get('test_duration', 0))  # Сохраняем длительность теста
    )

    # Привязка групп
    if group_ids:
        groups = Group.query.filter(Group.id.in_(group_ids)).all()
        lab.groups = groups

    db.session.add(lab)
    db.session.flush()  # чтобы получить lab.id

    # 2. сохраняем файлы
    lab_files = []
    files_dir = os.path.join("instance", "labs", str(lab.id))
    os.makedirs(files_dir, exist_ok=True)

    for idx, f in enumerate(files):
        name = f['name']
        b64 = f['base64'].split('base64,')[-1]  # на всякий случай
        content = base64.b64decode(b64)

        file_path = os.path.join(files_dir, name)
        with open(file_path, "wb") as fp:
            fp.write(content)

        lf = LabFile(
            lab_id=lab.id,
            file_path=file_path,
        )
        db.session.add(lf)
        lab_files.append(lf)

    db.session.flush()  # чтобы у lab_files были id

    # 3. создаём вопросы
    question_objs = []
    for q in questions:
        q_obj = Question(
            lab_id=lab.id,
            text=q['text'],
        )
        db.session.add(q_obj)
        question_objs.append(q_obj)

    db.session.flush()

    # 4. создаём ответы по файлам
    for q, q_obj in zip(questions, question_objs):
        for ans in q.get('answers', []):
            file_index = ans['file_index']
            correct_answer = ans['correct_answer'].strip()

            if file_index < 0 or file_index >= len(lab_files):
                continue

            fqa = FileQuestionAnswer(
                lab_file_id=lab_files[file_index].id,
                question_id=q_obj.id,
                correct_answer=correct_answer,
            )
            db.session.add(fqa)

    db.session.commit()
    return {'success': True}
