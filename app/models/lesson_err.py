from app import db
from datetime import datetime

class Lesson(db.Model):
    __tablename__ = 'lessons'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    trimester_id = db.Column(db.Integer, db.ForeignKey('trimesters.id', ondelete='CASCADE'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    offering = db.Column(db.Float, default=0.0)
    bibles = db.Column(db.Integer, default=0)
    magazines = db.Column(db.Integer, default=0)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(20), default='ABERTO')  # ABERTO, LIBERADO, FINALIZADO
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship('Attendance', backref='lesson', cascade='all, delete-orphan', lazy='dynamic')
    visitors        = db.relationship('Visitor',  backref='lesson', cascade='all, delete-orphan', lazy='dynamic')
    teacher         = db.relationship('Teacher', foreign_keys=[teacher_id], lazy='joined')
    extra_students  = db.relationship('Student', secondary='lesson_students', lazy='subquery')

# Tabela de alunos extras da aula (além dos da turma)
lesson_students = db.Table('lesson_students',
    db.Column('lesson_id',  db.Integer, db.ForeignKey('lessons.id',   ondelete='CASCADE'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('students.id',  ondelete='CASCADE'), primary_key=True)
)