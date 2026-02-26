from app import db
from datetime import datetime

class_teachers = db.Table('class_teachers',
    db.Column('class_id', db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), primary_key=True),
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), primary_key=True)
)

class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
