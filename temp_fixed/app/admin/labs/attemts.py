from flask import jsonify, render_template, redirect, url_for
from app.models import db, Group, Lab, Attempt, Student, Answer, Question, FileQuestionAnswer
from .__blueprint__ import admin_labs_bp


@admin_labs_bp.route("/labs/<int:lab_id>/groups/<int:group_id>")
def group_attempts(lab_id, group_id):
	lab = Lab.query.get_or_404(lab_id)
	group = Group.query.get_or_404(group_id)

	# Все студенты группы
	students = Student.query.filter_by(group_id=group.id).all()

	# Подготавливаем структуру для шаблона
	result = []

	for student in students:
		attempts = Attempt.query.filter_by(
			student_id=student.id,
			lab_id=lab.id
		).order_by(Attempt.started_at.desc()).all()

		result.append({
			"student_id": student.id,
			"student_name": f"{student.last_name} {student.first_name}",
			"attempts": [
				{
					"attempt_id": a.id,
					"started_at": a.started_at,
					"finished_at": a.finished_at,
					"score": a.score,
					"ip": a.ip,
					"user_agent": a.user_agent,
					"password_id": a.password_id,
					"file_id": a.password.file_id if a.password else None,
					"hash": a.watermark_hash

				}
				for a in attempts
			]
		})

	return render_template(
		"admin/attempts.html",
		lab=lab,
		group=group,
		students=result
	)


@admin_labs_bp.route("/attempts/<int:attempt_id>")
def show_attempt(attempt_id):
	attempt: Attempt = Attempt.query.filter_by(id=attempt_id).first()
	student: Student = Student.query.filter_by(id=attempt.student_id).first()
	answers: list[Answer] = Answer.query.filter_by(attempt_id=attempt_id).all()
	questsions: list[Question] = Question.query.filter_by(lab_id=attempt.lab_id).all()
	lab = Lab.query.get_or_404(attempt.lab_id)
	result = []
	for questsion in questsions:
		for answer in answers:
			if answer.question_id == questsion.id:
				file_question_answer: FileQuestionAnswer = FileQuestionAnswer.query.filter_by(question_id=questsion.id).first()
				result.append({'question': questsion.text, 'answer': answer.answer_text, 'true_answer': file_question_answer.correct_answer, 'correct': answer.is_correct})
	
	# Собираем информацию о нарушениях
	violations = {
		'tab_switches': attempt.violation_tab_switch or 0,
		'copy_detected': attempt.violation_copy or False,
		'fullscreen_exits': attempt.violation_fullscreen_exit or 0
	}
	
	return render_template("admin/one_attempt.html", results=result, student=student, lab=lab, violations=violations)


@admin_labs_bp.route("/labs/<int:lab_id>/students/<int:student_id>/reset", methods=["POST"])
def reset_attempts(lab_id, student_id):
	attempts = Attempt.query.filter_by(
		lab_id=lab_id,
		student_id=student_id
	).all()

	if not attempts:
		return redirect(url_for("admin.admin_labs.select_lab_and_group"))

	for attempt in attempts:
		# Удаляем ответы
		for ans in attempt.answers:
			db.session.delete(ans)

		db.session.delete(attempt)

	db.session.commit()

	return redirect(url_for("admin.admin_labs.select_lab_and_group"))


@admin_labs_bp.route("/attempts")
def select_lab_and_group():
	labs = Lab.query.order_by(Lab.title).all()
	return render_template(
		"admin/attempts_index.html",
		labs=labs
	)

