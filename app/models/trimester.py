from app import db
from datetime import datetime

class Trimester(db.Model):
    __tablename__ = 'trimesters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    weekdays = db.Column(db.String(20), nullable=True, default='0')  # comma-sep: 0=Mon,6=Sun
    lesson_prefix = db.Column(db.String(50), nullable=True, default='Lição')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lessons = db.relationship('Lesson', backref='trimester', cascade='all, delete-orphan', lazy='dynamic')
