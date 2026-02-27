from app import db
from datetime import datetime

class Church(db.Model):
    __tablename__ = 'churches'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    city       = db.Column(db.String(100), nullable=True)
    state      = db.Column(db.String(50),  nullable=True)
    active     = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    congregations = db.relationship('Congregation', backref='church', cascade='all, delete-orphan', lazy='dynamic')

class Congregation(db.Model):
    __tablename__ = 'congregations'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    city       = db.Column(db.String(100), nullable=True)
    address    = db.Column(db.String(255), nullable=True)
    church_id  = db.Column(db.Integer, db.ForeignKey('churches.id', ondelete='CASCADE'), nullable=False)
    active     = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
