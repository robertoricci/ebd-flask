from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.trimester import Trimester
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.klass import Class
from app.utils.decorators import admin_required
from app.utils.scope import scoped
from datetime import datetime, timedelta

trimesters_bp = Blueprint('trimesters', __name__, url_prefix='/trimestres')

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%d').date()
    except: return None

def _trimester_lesson_info(trimester_id, class_ids=None):
    """Retorna contagens de aulas do trimestre (opcionalmente filtrado por turmas)."""
    q = Lesson.query.filter_by(trimester_id=trimester_id)
    if class_ids is not None:
        q = q.filter(Lesson.class_id.in_(class_ids))
    total     = q.count()
    finalized = q.filter(Lesson.status == 'FINALIZADO').count()
    liberado  = q.filter(Lesson.status == 'LIBERADO').count()
    return {'total': total, 'finalized': finalized, 'liberado': liberado,
            'has_closed': finalized > 0 or liberado > 0}

@trimesters_bp.route('/')
@login_required
@admin_required
def index():
    trimesters = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter.desc()).all()
    now = datetime.now()

    # Para cada trimestre, calcular aulas da congregação do usuário
    cong_class_ids = [c.id for c in scoped(Class).all()]
    trimester_info = {}
    for t in trimesters:
        info = _trimester_lesson_info(t.id, cong_class_ids if cong_class_ids else None)
        trimester_info[t.id] = info

    return render_template('trimesters/index.html', trimesters=trimesters, now=now,
                           trimester_info=trimester_info)

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
    # Verificar se há lições finalizadas ou liberadas em qualquer turma
    info = _trimester_lesson_info(t.id)
    if info['has_closed']:
        flash(f'❌ Não é possível excluir: este trimestre possui {info["finalized"]} aula(s) FINALIZADA(S) e {info["liberado"]} LIBERADA(S).', 'danger')
        return redirect(url_for('trimesters.index'))
    db.session.delete(t)
    db.session.commit()
    flash('Trimestre removido com sucesso.', 'success')
    return redirect(url_for('trimesters.index'))

@trimesters_bp.route('/<int:id>/generate', methods=['POST'])
@login_required
@admin_required
def generate(id):
    t = Trimester.query.get_or_404(id)
    classes = scoped(Class).all()

    if not classes:
        flash('Nenhuma turma encontrada na sua congregação.', 'warning')
        return redirect(url_for('trimesters.index'))

    # Bloquear se já existem aulas geradas para este trimestre nesta congregação
    cong_class_ids = [c.id for c in classes]
    info = _trimester_lesson_info(t.id, cong_class_ids)
    if info['total'] > 0:
        flash(f'❌ Este trimestre já possui {info["total"]} aula(s) gerada(s) para sua congregação. Exclua-as antes de gerar novamente.', 'danger')
        return redirect(url_for('trimesters.index'))

    weekdays = [int(d) for d in t.weekdays.split(',') if d.strip().isdigit()]
    current = t.start_date
    lesson_num = 1
    lessons_created = 0

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
                lessons_created += 1
            lesson_num += 1
        current += timedelta(days=1)

    db.session.commit()
    cong_name = current_user.congregation.name if current_user.congregation else 'sua congregação'
    flash(f'✅ {lessons_created} aulas geradas para {cong_name}!', 'success')
    return redirect(url_for('trimesters.index'))