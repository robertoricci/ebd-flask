from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models.visitor import Visitor

visitors_bp = Blueprint('visitors', __name__, url_prefix='/visitantes')

@visitors_bp.route('/create', methods=['POST'])
@login_required
def create():
    v = Visitor(
        lesson_id=request.form.get('lesson_id', type=int),
        name=request.form.get('name', '').strip(),
        phone=request.form.get('phone', '').strip() or None,
        church=request.form.get('church', '').strip() or None,
        notes=request.form.get('notes', '').strip() or None
    )
    db.session.add(v)
    db.session.commit()
    lesson_id = v.lesson_id
    return redirect(url_for('attendance.index', lesson_id=lesson_id))

@visitors_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    v = Visitor.query.get_or_404(id)
    lesson_id = v.lesson_id
    db.session.delete(v)
    db.session.commit()
    return redirect(url_for('attendance.index', lesson_id=lesson_id))
