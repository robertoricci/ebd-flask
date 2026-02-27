from app import db
from app.models.teacher import class_teachers
from app.models.student import class_students
from datetime import datetime

class Class(db.Model):
    __tablename__ = 'classes'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    description     = db.Column(db.Text,        nullable=True)
    congregation_id = db.Column(db.Integer, db.ForeignKey('congregations.id', ondelete='SET NULL'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    congregation = db.relationship('Congregation', foreign_keys=[congregation_id], lazy='joined')
    teachers  = db.relationship('Teacher', secondary=class_teachers, backref='classes', lazy='subquery')
    students  = db.relationship('Student', secondary=class_students, backref='classes', lazy='subquery')
    lessons   = db.relationship('Lesson',  backref='klass', cascade='all, delete-orphan', lazy='dynamic')
