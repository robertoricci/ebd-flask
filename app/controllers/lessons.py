from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.klass import Class
from app.models.trimester import Trimester
from app.utils.decorators import admin_required
from datetime import datetime

lessons_bp = Blueprint('lessons', __name__, url_prefix='/aulas')

STATUS_ORDER = ['ABERTO', 'LIBERADO', 'FINALIZADO']

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%d').date()
    except: return None

@lessons_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = Lesson.query
    if search:
        q = q.filter(Lesson.title.ilike(f'%{search}%'))
    lessons = q.order_by(Lesson.date.desc()).all()
    classes = Class.query.order_by(Class.name).all()
    trimesters = Trimester.query.order_by(Trimester.year.desc()).all()
    return render_template('lessons/index.html', lessons=lessons, classes=classes, trimesters=trimesters, search=search)

@lessons_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    class_id = int(request.form.get('class_id'))
    lesson = Lesson(
        title=request.form.get('title', '').strip(),
        date=parse_date(request.form.get('date')),
        class_id=class_id,
        trimester_id=request.form.get('trimester_id', type=int) or None,
        description=request.form.get('description', '').strip() or None,
        offering=float(request.form.get('offering', 0) or 0),
        status='ABERTO'
    )
    db.session.add(lesson)
    db.session.flush()
    klass = Class.query.get(class_id)
    for student in klass.students:
        att = Attendance(lesson_id=lesson.id, student_id=student.id, present=False)
        db.session.add(att)
    db.session.commit()
    flash('Aula criada!', 'success')
    return redirect(url_for('lessons.index'))

@lessons_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    l = Lesson.query.get_or_404(id)
    l.title = request.form.get('title', l.title).strip()
    l.date = parse_date(request.form.get('date')) or l.date
    l.class_id = request.form.get('class_id', l.class_id, type=int)
    l.trimester_id = request.form.get('trimester_id', type=int) or None
    l.description = request.form.get('description', '').strip() or None
    l.offering = float(request.form.get('offering', 0) or 0)
    db.session.commit()
    flash('Aula atualizada!', 'success')
    return redirect(url_for('lessons.index'))

@lessons_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    l = Lesson.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    flash('Aula removida.', 'success')
    return redirect(url_for('lessons.index'))

@lessons_bp.route('/<int:id>/advance', methods=['POST'])
@login_required
@admin_required
def advance(id):
    l = Lesson.query.get_or_404(id)
    idx = STATUS_ORDER.index(l.status)
    if idx < len(STATUS_ORDER) - 1:
        l.status = STATUS_ORDER[idx + 1]
        db.session.commit()
    flash(f'Status: {l.status}', 'success')
    return redirect(url_for('lessons.index'))

@lessons_bp.route('/<int:id>/retreat', methods=['POST'])
@login_required
@admin_required
def retreat(id):
    l = Lesson.query.get_or_404(id)
    idx = STATUS_ORDER.index(l.status)
    if idx > 0:
        l.status = STATUS_ORDER[idx - 1]
        db.session.commit()
    flash(f'Status: {l.status}', 'success')
    return redirect(url_for('lessons.index'))
