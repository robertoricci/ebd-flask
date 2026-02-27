from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.klass import Class
from app.models.trimester import Trimester
from app.utils.decorators import admin_required
from app.utils.scope import scoped, scoped_lessons
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
    q = scoped_lessons()
    if search:
        q = q.filter(Lesson.title.ilike(f'%{search}%'))
    lessons = q.order_by(Lesson.date.desc()).all()

    # Só turmas e trimestres da congregação do usuário
    classes    = scoped(Class).order_by(Class.name).all()
    trimesters = Trimester.query.order_by(Trimester.year.desc()).all()
    return render_template('lessons/index.html', lessons=lessons, classes=classes,
                           trimesters=trimesters, search=search)

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

@lessons_bp.route('/<int:id>/set-status', methods=['POST'])
@login_required
@admin_required
def set_status(id):
    l = Lesson.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in STATUS_ORDER:
        l.status = new_status
        db.session.commit()
    return jsonify({'status': l.status})