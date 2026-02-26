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
    status = db.Column(db.String(20), default='ABERTO')  # ABERTO, LIBERADO, FINALIZADO
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship('Attendance', backref='lesson', cascade='all, delete-orphan', lazy='dynamic')
    visitors = db.relationship('Visitor', backref='lesson', cascade='all, delete-orphan', lazy='dynamic')
