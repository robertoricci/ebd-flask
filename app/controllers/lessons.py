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
    search       = request.args.get('q', '').strip()
    year         = request.args.get('year', type=int)
    trimester_id = request.args.get('trimester_id', type=int)

    q = scoped_lessons()

    if search:
        q = q.filter(Lesson.title.ilike(f'%{search}%'))
    if trimester_id:
        q = q.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        q = q.filter(Lesson.trimester_id.in_(t_ids)) if t_ids else q.filter(db.false())

    lessons = q.order_by(Lesson.date.desc()).all()

    # Anos disponíveis a partir dos trimestres existentes
    years = [r[0] for r in db.session.query(Trimester.year).distinct().order_by(Trimester.year.desc()).all()]

    # Trimestres filtrados pelo ano selecionado
    tq = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter)
    if year:
        tq = tq.filter_by(year=year)
    trimesters = tq.all()

    classes = scoped(Class).order_by(Class.name).all()
    all_trimesters = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter).all()

    return render_template('lessons/index.html',
        lessons=lessons, classes=classes,
        trimesters=trimesters, all_trimesters=all_trimesters,
        years=years, year=year, trimester_id=trimester_id, search=search)

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