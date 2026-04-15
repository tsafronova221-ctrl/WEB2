import random
from flask import render_template, request, redirect, url_for, jsonify, abort, Blueprint
from app import db
from app.models import (
    Student,
    Group,
    Lab,
    LabFile,
    Question,
    Attempt,
    Answer,
    LabPassword,
    FileQuestionAnswer
)
from app.security import generate_watermark_hash, sanitize_filename
from datetime import datetime, timedelta
import pytz
import re

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')

public_bp = Blueprint("public", __name__)


def validate_student_name(name):
    """Валидация имени студента"""
    if not name or not isinstance(name, str):
        return False, "Имя не может быть пустым"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Имя должно содержать минимум 2 символа"
    
    if len(name) > 64:
        return False, "Имя должно содержать максимум 64 символа"
    
    # Разрешаем только буквы и пробелы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s\-]+$', name):
        return False, "Имя содержит недопустимые символы"
    
    return True, name


def validate_password(password):
    """Валидация пароля варианта"""
    if not password or not isinstance(password, str):
        return False, "Пароль не может быть пустым"
    
    password = password.strip().upper()
    
    if len(password) < 5 or len(password) > 20:
        return False, "Некорректная длина пароля"
    
    return True, password


@public_bp.route("/")
def index():
    groups = Group.query.all()
    return render_template("public/index.html", groups=groups)


@public_bp.route("/start", methods=["POST"])
def start():
    # Валидация входных данных
    last_raw = request.form.get("last_name", "")
    first_raw = request.form.get("first_name", "")
    group_id_raw = request.form.get("group_id")
    password_raw = request.form.get("password", "")

    # Валидация фамилии
    valid, result = validate_student_name(last_raw)
    if not valid:
        all_groups = Group.query.all()
        return render_template("public/index.html", groups=all_groups, error=result)
    last = result

    # Валидация имени
    valid, result = validate_student_name(first_raw)
    if not valid:
        all_groups = Group.query.all()
        return render_template("public/index.html", groups=all_groups, error=result)
    first = result

    # Валидация пароля
    valid, password = validate_password(password_raw)
    if not valid:
        all_groups = Group.query.all()
        return render_template("public/index.html", groups=all_groups, error="Неверный формат пароля")

    # Валидация group_id если предоставлен
    group_id = None
    if group_id_raw:
        try:
            group_id = int(group_id_raw)
            if group_id < 1 or group_id > 100000:
                all_groups = Group.query.all()
                return render_template("public/index.html", groups=all_groups, error="Некорректный ID группы")
        except (ValueError, TypeError):
            all_groups = Group.query.all()
            return render_template("public/index.html", groups=all_groups, error="Некорректный ID группы")

    # 1. Ищем пароль варианта
    lp = LabPassword.query.filter_by(password=password).first()

    # Список групп нужен для рендера страницы ошибки, если что-то пойдет не так
    all_groups = Group.query.all()

    if not lp:
        return render_template(
            "public/index.html",
            groups=all_groups,
            error="Неверный пароль варианта",
        )

    # Получаем саму лабораторную работу
    lab = Lab.query.get(lp.lab_id)
    
    if not lab:
        return render_template(
            "public/index.html",
            groups=all_groups,
            error="Работа не найдена",
        )

    # --- ПРОВЕРКА: ДОСТУП ГРУППЫ ---
    if group_id:
        allowed_group_ids = [g.id for g in lab.groups]
        if group_id not in allowed_group_ids:
            return render_template(
                "public/index.html",
                groups=all_groups,
                error="Эта работа недоступна для выбранной группы",
            )
    # -------------------------------------
    
    # Проверка дедлайнов
    now = datetime.now(MSK)
    
    start_at = MSK.localize(lab.start_at) if lab.start_at and lab.start_at.tzinfo is None else lab.start_at
    deadline_at = MSK.localize(lab.deadline_at) if lab.deadline_at and lab.deadline_at.tzinfo is None else lab.deadline_at
    
    if start_at and start_at > now:
        return render_template("public/index.html", groups=all_groups, error="Время выполнения работы еще не наступило")

    if deadline_at and now > deadline_at:
        return render_template("public/index.html", groups=all_groups, error="Срок сдачи работы истек")

    # 2. Ищем или создаём студента
    student_query = Student.query.filter_by(
        last_name=last,
        first_name=first,
    )
    if group_id:
        student_query = student_query.filter_by(group_id=group_id)

    student = student_query.first()
    if not student:
        student = Student(
            last_name=last,
            first_name=first,
            group_id=group_id if group_id else None,
        )
        db.session.add(student)
        db.session.commit()

    # === ПРОВЕРКА НА АКТИВНУЮ ПОПЫТКУ ===
    existing_attempt = Attempt.query.filter_by(
        student_id=student.id,
        lab_id=lab.id,
        password_id=lp.id
    ).first()
    
    if existing_attempt:
        if existing_attempt.finished_at is not None:
            return render_template(
                "public/index.html",
                groups=all_groups,
                error="Вы уже выполняли эту работу. Повторная попытка невозможна.",
            )
        
        now = datetime.now(MSK)
        attempt_started = existing_attempt.started_at
        if attempt_started.tzinfo is None:
            attempt_started = MSK.localize(attempt_started)
        
        # Если попытка была начата очень давно (>24 часов) - удаляем
        if (now - attempt_started).total_seconds() > 24 * 3600:
            db.session.delete(existing_attempt)
            db.session.commit()
        elif lab.is_test and lab.test_duration and lab.test_duration > 0:
            elapsed = now - attempt_started
            max_duration_seconds = lab.test_duration * 60
            
            if elapsed.total_seconds() >= max_duration_seconds:
                existing_attempt.finished_at = now
                existing_attempt.score = 0
                db.session.commit()
                return render_template(
                    "public/index.html",
                    groups=all_groups,
                    error="Время на выполнение работы истекло. Вы не можете начать новую попытку.",
                )
            else:
                lab_file = LabFile.query.get(lp.file_id)
                question_ids = [answer.question_id for answer in existing_attempt.answers]
                questions = Question.query.filter(Question.id.in_(question_ids)).all()
                
                questions_ordered = []
                for ans in existing_attempt.answers:
                    for q in questions:
                        if q.id == ans.question_id:
                            questions_ordered.append(q)
                            break
                
                remaining_seconds = int(max_duration_seconds - elapsed.total_seconds())
                
                return render_template(
                    "public/questions.html",
                    attempt=existing_attempt,
                    lab_file=lab_file,
                    questions=questions_ordered,
                    lab=lab,
                    remaining_time=remaining_seconds
                )
        else:
            lab_file = LabFile.query.get(lp.file_id)
            question_ids = [answer.question_id for answer in existing_attempt.answers]
            questions = Question.query.filter(Question.id.in_(question_ids)).all()
            
            questions_ordered = []
            for ans in existing_attempt.answers:
                for q in questions:
                    if q.id == ans.question_id:
                        questions_ordered.append(q)
                        break
            
            return render_template(
                "public/questions.html",
                attempt=existing_attempt,
                lab_file=lab_file,
                questions=questions_ordered,
                lab=lab
            )
    # ====================================

    lab_file = LabFile.query.get(lp.file_id)

    # 3. Создаём попытку
    attempt = Attempt(
        student_id=student.id,
        lab_id=lab.id,
        password_id=lp.id,
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        started_at=datetime.now(MSK),
    )
    db.session.add(attempt)
    db.session.flush()

    # ЛОГИКА ВЫБОРА ВОПРОСОВ
    all_questions = Question.query.filter_by(lab_id=lab.id).all()
    selected_questions = []

    if lab.is_test and lab.questions_count > 0:
        count = min(len(all_questions), lab.questions_count)
        selected_questions = random.sample(all_questions, count)
    else:
        selected_questions = all_questions

    # Создаем пустые ответы
    for q in selected_questions:
        empty_answer = Answer(
            attempt_id=attempt.id,
            question_id=q.id,
            answer_text="",
            is_correct=False
        )
        db.session.add(empty_answer)

    db.session.commit()

    return render_template(
        "public/questions.html",
        attempt=attempt,
        lab_file=lab_file,
        questions=selected_questions,
        lab=lab
    )


@public_bp.route("/finish/<int:attempt_id>", methods=["POST"])
def finish(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)
    
    # ===== ЗАЩИТА ОТ ПОВТОРНОЙ ОТПРАВКИ =====
    if attempt.finished_at is not None:
        lab_file_id = attempt.password.file_id
        correct_map = {
            fqa.question_id: fqa.correct_answer
            for fqa in FileQuestionAnswer.query.filter_by(lab_file_id=lab_file_id)
        }

        results_list = []
        for answer_record in attempt.answers:
            q = answer_record.question
            correct_text = (correct_map.get(q.id) or "").strip()
            if answer_record.is_correct:
                results_list.append(['correct', q.text])
            else:
                results_list.append(['wrong', q.text])
        
        return render_template("public/finish.html", attempt=attempt, answers=results_list)
    # ========================================
    
    # ===== СОХРАНЕНИЕ ДАННЫХ О НАРУШЕНИЯХ =====
    if attempt.lab.is_test:
        try:
            tab_switches = request.form.get('violation_tab_switch', 0, type=int)
            copy_detected = request.form.get('violation_copy', '0') == '1'
            fullscreen_exits = request.form.get('violation_fullscreen_exit', 0, type=int)
            
            # Ограничиваем значения разумными пределами
            tab_switches = max(0, min(10000, tab_switches))
            fullscreen_exits = max(0, min(10000, fullscreen_exits))
            
            attempt.violation_tab_switch = tab_switches
            attempt.violation_copy = copy_detected
            attempt.violation_fullscreen_exit = fullscreen_exits
        except (ValueError, TypeError):
            pass
    # ========================================
    
    lab_file_id = attempt.password.file_id
    correct_map = {
        fqa.question_id: fqa.correct_answer
        for fqa in FileQuestionAnswer.query.filter_by(lab_file_id=lab_file_id)
    }

    score = 0
    results_list = []

    for answer_record in attempt.answers:
        q = answer_record.question
        ans_text = request.form.get(f"q{q.id}", "").strip()
        correct_text = (correct_map.get(q.id) or "").strip()

        # Ограничение длины ответа
        if len(ans_text) > 512:
            ans_text = ans_text[:512]

        is_correct = ans_text.lower() == correct_text.lower()

        if is_correct:
            score += 1
            results_list.append(['correct', q.text])
        else:
            results_list.append(['wrong', q.text])

        answer_record.answer_text = ans_text
        answer_record.is_correct = is_correct

    attempt.score = score
    attempt.finished_at = datetime.now(MSK)
    attempt.watermark_hash = generate_watermark_hash(attempt)
    db.session.commit()

    return render_template("public/finish.html", attempt=attempt, answers=results_list)


@public_bp.route("/auto-finish/<int:attempt_id>", methods=["POST"])
def auto_finish(attempt_id):
    """Автоматическое завершение попытки по истечении времени с сохранением нарушений"""
    attempt = Attempt.query.get_or_404(attempt_id)
    
    if attempt.finished_at is not None:
        return redirect(url_for('public.finish', attempt_id=attempt_id))
    
    # ===== СОХРАНЕНИЕ ДАННЫХ О НАРУШЕНИЯХ =====
    if attempt.lab.is_test:
        try:
            tab_switches = request.form.get('violation_tab_switch', 0, type=int)
            copy_detected = request.form.get('violation_copy', '0') == '1'
            fullscreen_exits = request.form.get('violation_fullscreen_exit', 0, type=int)
            
            tab_switches = max(0, min(10000, tab_switches))
            fullscreen_exits = max(0, min(10000, fullscreen_exits))
            
            attempt.violation_tab_switch = tab_switches
            attempt.violation_copy = copy_detected
            attempt.violation_fullscreen_exit = fullscreen_exits
        except (ValueError, TypeError):
            pass
    # ========================================
    
    attempt.score = 0
    attempt.finished_at = datetime.now(MSK)
    attempt.watermark_hash = generate_watermark_hash(attempt)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Время вышло, работа завершена автоматически',
        'violations_saved': attempt.lab.is_test
    })
