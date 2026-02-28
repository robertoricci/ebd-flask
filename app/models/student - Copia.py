from app import db
from datetime import datetime

class_students = db.Table('class_students',
    db.Column('class_id',   db.Integer, db.ForeignKey('classes.id',   ondelete='CASCADE'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('students.id',  ondelete='CASCADE'), primary_key=True)
)

class Student(db.Model):
    __tablename__ = 'students'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    email           = db.Column(db.String(150), nullable=True)
    phone           = db.Column(db.String(30),  nullable=True)
    birth_date      = db.Column(db.Date,        nullable=True)
    notes           = db.Column(db.Text,        nullable=True)
    congregation_id = db.Column(db.Integer, db.ForeignKey('congregations.id', ondelete='SET NULL'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    congregation = db.relationship('Congregation', foreign_keys=[congregation_id], lazy='joined')
    attendances  = db.relationship('Attendance', backref='student', cascade='all, delete-orphan', lazy='dynamic')
