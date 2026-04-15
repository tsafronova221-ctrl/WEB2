from . import db
from datetime import datetime, timezone
import pytz

# Часовой пояс Москвы
MSK = pytz.timezone('Europe/Moscow')


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    size = db.Column(db.Integer)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(64))
    first_name = db.Column(db.String(64))
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))

    group = db.relationship("Group", backref="students")


class Lab(db.Model):
    __tablename__ = "labs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    code = db.Column(db.String(32))
    start_at = db.Column(db.DateTime)
    deadline_at = db.Column(db.DateTime)
    description = db.Column(db.Text)
    is_test = db.Column(db.Boolean, default=False)  # True = Контрольная, False = ЛР
    questions_count = db.Column(db.Integer, default=0)  # Сколько вопросов выдавать (0 = все)
    test_duration = db.Column(db.Integer, default=0)  # Время на тест в минутах (0 = не ограничено)

    groups = db.relationship("Group", secondary="lab_groups", backref="labs")


lab_groups = db.Table(
    "lab_groups",
    db.Column("lab_id", db.Integer, db.ForeignKey("labs.id")),
    db.Column("group_id", db.Integer, db.ForeignKey("groups.id"))
)


class LabFile(db.Model):
    __tablename__ = "lab_files"

    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"))
    file_path = db.Column(db.String(256))

    lab = db.relationship("Lab", backref="files")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"))
    text = db.Column(db.String(512))

    lab = db.relationship("Lab", backref="questions")


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"))
    password_id = db.Column(db.Integer, db.ForeignKey("lab_passwords.id"))  # ← тут главное изменение
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(MSK))
    finished_at = db.Column(db.DateTime, default=None)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(256))
    score = db.Column(db.Integer)
    watermark_hash = db.Column(db.String(128))
    violation_tab_switch = db.Column(db.Integer, default=0)  # Количество переключений вкладок
    violation_copy = db.Column(db.Boolean, default=False)  # Было ли копирование
    violation_fullscreen_exit = db.Column(db.Integer, default=0)  # Выходы из полноэкранного режима

    student = db.relationship("Student", backref="attempts")
    lab = db.relationship("Lab", backref="attempts")
    password = db.relationship("LabPassword", backref="attempts")  # ← теперь к LabPassword


class Answer(db.Model):
    __tablename__ = "answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"))
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"))
    answer_text = db.Column(db.String(512))
    is_correct = db.Column(db.Boolean)

    attempt = db.relationship("Attempt", backref="answers")
    question = db.relationship("Question", backref="answers")


class FileQuestionAnswer(db.Model):
    __tablename__ = "file_question_answers"

    id = db.Column(db.Integer, primary_key=True)
    lab_file_id = db.Column(db.Integer, db.ForeignKey("lab_files.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    correct_answer = db.Column(db.String(256), nullable=False)

    file = db.relationship("LabFile", backref="question_answers")


class LabPassword(db.Model):
    __tablename__ = "lab_passwords"
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey("labs.id"), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("lab_files.id"), nullable=False)
    password = db.Column(db.String(64), nullable=False, unique=True)

    lab = db.relationship("Lab", backref="passwords")
    file = db.relationship("LabFile", backref="passwords")
