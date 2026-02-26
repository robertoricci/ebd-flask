from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.trimester import Trimester
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.klass import Class
from app.utils.decorators import admin_required
from datetime import datetime, timedelta

trimesters_bp = Blueprint('trimesters', __name__, url_prefix='/trimestres')

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%d').date()
    except: return None

@trimesters_bp.route('/')
@login_required
@admin_required
def index():
    trimesters = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter.desc()).all()
    return render_template('trimesters/index.html', trimesters=trimesters)

@trimesters_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    weekdays = ','.join(request.form.getlist('weekdays'))
    t = Trimester(
        name=request.form.get('name', '').strip(),
        year=int(request.form.get('year', datetime.now().year)),
        quarter=int(request.form.get('quarter', 1)),
        start_date=parse_date(request.form.get('start_date')),
        end_date=parse_date(request.form.get('end_date')),
        weekdays=weekdays or '6',
        lesson_prefix=request.form.get('lesson_prefix', 'Lição').strip()
    )
    db.session.add(t)
    db.session.commit()
    flash('Trimestre criado!', 'success')
    return redirect(url_for('trimesters.index'))

@trimesters_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    t = Trimester.query.get_or_404(id)
    weekdays = ','.join(request.form.getlist('weekdays'))
    t.name = request.form.get('name', t.name).strip()
    t.year = int(request.form.get('year', t.year))
    t.quarter = int(request.form.get('quarter', t.quarter))
    t.start_date = parse_date(request.form.get('start_date')) or t.start_date
    t.end_date = parse_date(request.form.get('end_date')) or t.end_date
    t.weekdays = weekdays or t.weekdays
    t.lesson_prefix = request.form.get('lesson_prefix', t.lesson_prefix).strip()
    db.session.commit()
    flash('Trimestre atualizado!', 'success')
    return redirect(url_for('trimesters.index'))

@trimesters_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    t = Trimester.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Trimestre removido.', 'success')
    return redirect(url_for('trimesters.index'))

@trimesters_bp.route('/<int:id>/generate', methods=['POST'])
@login_required
@admin_required
def generate(id):
    t = Trimester.query.get_or_404(id)
    classes = Class.query.all()
    weekdays = [int(d) for d in t.weekdays.split(',') if d.strip().isdigit()]
    
    current = t.start_date
    count = 0
    lesson_num = 1
    
    while current <= t.end_date:
        if current.weekday() in weekdays:
            for c in classes:
                lesson = Lesson(
                    title=f'{t.lesson_prefix} {lesson_num}',
                    date=current,
                    class_id=c.id,
                    trimester_id=t.id,
                    status='ABERTO'
                )
                db.session.add(lesson)
                db.session.flush()
                for student in c.students:
                    att = Attendance(lesson_id=lesson.id, student_id=student.id, present=False)
                    db.session.add(att)
                count += 1
            lesson_num += 1
        current += timedelta(days=1)
    
    db.session.commit()
    flash(f'✅ {count} aulas geradas com sucesso!', 'success')
    return redirect(url_for('trimesters.index'))
