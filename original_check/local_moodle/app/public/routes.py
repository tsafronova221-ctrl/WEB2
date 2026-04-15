import random

from flask import Blueprint, render_template, request, redirect, url_for
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
from app.security import generate_watermark_hash
from datetime import datetime
import pytz

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    groups = Group.query.all()
    return render_template("public/index.html", groups=groups)


@public_bp.route("/start", methods=["POST"])
def start():
    last = request.form["last_name"].strip()
    first = request.form["first_name"].strip()
    group_id = request.form.get("group_id")
    password = request.form["password"].strip().upper()

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

    # --- НОВАЯ ПРОВЕРКА: ДОСТУП ГРУППЫ ---
    # Проверяем, привязана ли выбранная студентом группа к этой лабораторной
    if group_id:
        selected_group_id = int(group_id)
        # Получаем список ID разрешенных групп
        allowed_group_ids = [g.id for g in lab.groups]

        if selected_group_id not in allowed_group_ids:
            return render_template(
                "public/index.html",
                groups=all_groups,
                error="Эта работа недоступна для выбранной группы",
            )
    # -------------------------------------
    
    # Проверка дедлайнов (перенес выше, до создания студента)
    now = datetime.now(MSK)  # Используем московское время для всех проверок
    
    # Приводим даты из БД к московскому времени с правильным часовым поясом
    # Используем localize вместо replace, чтобы получить правильное смещение +03:00
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
    # Ищем любую попытку для этого студента и этой работы (с этим паролем)
    existing_attempt = Attempt.query.filter_by(
        student_id=student.id,
        lab_id=lab.id,
        password_id=lp.id
    ).first()
    
    if existing_attempt:
        # Если есть любая попытка - проверяем её статус
        if existing_attempt.finished_at is not None:
            # Попытка уже завершена - нельзя начать новую
            return render_template(
                "public/index.html",
                groups=all_groups,
                error="Вы уже выполняли эту работу. Повторная попытка невозможна.",
            )
        
        # Попытка активна (finished_at == None) - проверяем время
        from datetime import timedelta
        now = datetime.now(MSK)  # Используем московское время
        
        # Приводим started_at к тому же формату (с часовым поясом)
        attempt_started = existing_attempt.started_at
        if attempt_started.tzinfo is None:
            attempt_started = MSK.localize(attempt_started)
        
        # Если попытка была начата очень давно (больше 24 часов назад), считаем её "заброшенной"
        # и разрешаем создать новую (это защита от зависших попыток)
        if (now - attempt_started).total_seconds() > 24 * 3600:
            # Удаляем старую заброшенную попытку и создаем новую
            db.session.delete(existing_attempt)
            db.session.commit()
            # Продолжаем код ниже для создания новой попытки
        elif lab.is_test and lab.test_duration and lab.test_duration > 0:
            # Вычисляем время начала попытки с учетом длительности теста
            # Студент должен уложиться в test_duration минут с момента started_at
            elapsed = now - attempt_started
            max_duration_seconds = lab.test_duration * 60
            
            if elapsed.total_seconds() >= max_duration_seconds:
                # Время истекло - завершаем попытку автоматически с сохранением нарушений
                existing_attempt.finished_at = now
                existing_attempt.score = 0
                db.session.commit()
                # Возвращаем ошибку, что время вышло
                return render_template(
                    "public/index.html",
                    groups=all_groups,
                    error="Время на выполнение работы истекло. Вы не можете начать новую попытку.",
                )
            else:
                # Если время еще есть - перенаправляем на продолжение
                lab_file = LabFile.query.get(lp.file_id)
                
                # Получаем вопросы для этой попытки
                question_ids = [answer.question_id for answer in existing_attempt.answers]
                questions = Question.query.filter(Question.id.in_(question_ids)).all()
                
                # Сохраняем порядок вопросов как в attempt.answers
                questions_ordered = []
                for ans in existing_attempt.answers:
                    for q in questions:
                        if q.id == ans.question_id:
                            questions_ordered.append(q)
                            break
                
                # Пересчитываем оставшееся время для фронтенда
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
            # Для ЛР без таймера - просто продолжаем попытку
            lab_file = LabFile.query.get(lp.file_id)
            
            # Получаем вопросы для этой попытки
            question_ids = [answer.question_id for answer in existing_attempt.answers]
            questions = Question.query.filter(Question.id.in_(question_ids)).all()
            
            # Сохраняем порядок вопросов как в attempt.answers
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
        started_at=datetime.now(MSK),  # Используем московское время
    )
    db.session.add(attempt)
    db.session.flush()  # flush, чтобы получить attempt.id до коммита

    # ЛОГИКА ВЫБОРА ВОПРОСОВ
    all_questions = Question.query.filter_by(lab_id=lab.id).all()
    selected_questions = []

    if lab.is_test and lab.questions_count > 0:
        # Если это КР и задано кол-во вопросов, берем случайные
        count = min(len(all_questions), lab.questions_count)
        selected_questions = random.sample(all_questions, count)
    else:
        # Иначе (ЛР) берем все вопросы
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
    # Если попытка уже была завершена (finished_at заполнено),
    # то просто показываем страницу завершения с данными этой попытки
    if attempt.finished_at is not None:
        # Не создаем новую попытку, а просто показываем результаты старой
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
        # Получаем данные о нарушениях из формы
        tab_switches = request.form.get('violation_tab_switch', 0, type=int)
        copy_detected = request.form.get('violation_copy', '0') == '1'
        fullscreen_exits = request.form.get('violation_fullscreen_exit', 0, type=int)
        
        # Сохраняем в базу данных
        attempt.violation_tab_switch = tab_switches
        attempt.violation_copy = copy_detected
        attempt.violation_fullscreen_exit = fullscreen_exits
    # ========================================
    
    lab_file_id = attempt.password.file_id
    correct_map = {
        fqa.question_id: fqa.correct_answer
        for fqa in FileQuestionAnswer.query.filter_by(lab_file_id=lab_file_id)
    }

    score = 0
    results_list = []

    # Итерируемся по УЖЕ СОЗДАННЫМ (в start) ответам этой попытки
    # Это гарантирует, что студент отвечает только на выданные ему вопросы
    for answer_record in attempt.answers:
        q = answer_record.question

        # Получаем ответ студента из формы
        ans_text = request.form.get(f"q{q.id}", "").strip()
        correct_text = (correct_map.get(q.id) or "").strip()

        is_correct = ans_text.lower() == correct_text.lower()

        if is_correct:
            score += 1
            results_list.append(['correct', q.text])
        else:
            results_list.append(['wrong', q.text])

        # Обновляем запись в БД
        answer_record.answer_text = ans_text
        answer_record.is_correct = is_correct

    attempt.score = score
    attempt.finished_at = datetime.now(MSK)  # Используем московское время
    attempt.watermark_hash = generate_watermark_hash(attempt)
    db.session.commit()

    return render_template("public/finish.html", attempt=attempt, answers=results_list)


@public_bp.route("/auto-finish/<int:attempt_id>", methods=["POST"])
def auto_finish(attempt_id):
    """Автоматическое завершение попытки по истечении времени с сохранением нарушений"""
    attempt = Attempt.query.get_or_404(attempt_id)
    
    # Если уже завершена - возвращаем ошибку
    if attempt.finished_at is not None:
        return redirect(url_for('public.finish', attempt_id=attempt_id))
    
    # ===== СОХРАНЕНИЕ ДАННЫХ О НАРУШЕНИЯХ =====
    if attempt.lab.is_test:
        # Получаем данные о нарушениях из формы
        tab_switches = request.form.get('violation_tab_switch', 0, type=int)
        copy_detected = request.form.get('violation_copy', '0') == '1'
        fullscreen_exits = request.form.get('violation_fullscreen_exit', 0, type=int)
        
        # Сохраняем в базу данных
        attempt.violation_tab_switch = tab_switches
        attempt.violation_copy = copy_detected
        attempt.violation_fullscreen_exit = fullscreen_exits
    # ========================================
    
    # Завершаем попытку с нулевым баллом (так как время вышло)
    attempt.score = 0
    attempt.finished_at = datetime.now(MSK)  # Используем московское время
    attempt.watermark_hash = generate_watermark_hash(attempt)
    db.session.commit()
    
    # Возвращаем JSON для AJAX запроса
    from flask import jsonify
    return jsonify({
        'status': 'success',
        'message': 'Время вышло, работа завершена автоматически',
        'violations_saved': attempt.lab.is_test
    })
