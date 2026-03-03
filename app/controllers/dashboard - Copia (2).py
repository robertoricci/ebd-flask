from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.trimester import Trimester
from app.models.klass import Class
from app.models.student import Student, class_students
from app.models.teacher import Teacher
from app.models.church import Congregation
from app.utils.scope import congregation_ids
from datetime import date
from sqlalchemy import func, select
import re

dashboard_bp = Blueprint('dashboard', __name__)


def _natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s or '')]


def _enrolled_count(class_id):
    return db.session.execute(
        select(func.count()).select_from(class_students).where(
            class_students.c.class_id == class_id
        )
    ).scalar() or 0


@dashboard_bp.route('/dashboard')
@login_required
def index():
    cong_ids = congregation_ids()

    # ── Filtros ──────────────────────────────────────────────────────────
    congregation_id = request.args.get('congregation_id', type=int)
    year            = request.args.get('year',            type=int)
    trimester_id    = request.args.get('trimester_id',    type=int)
    lesson_title    = request.args.get('lesson_title',    '').strip()
    class_id        = request.args.get('class_id',        type=int)

    # Congregações disponíveis para filtro (superadmin / church_admin)
    show_cong_filter = current_user.is_superadmin or current_user.is_church_admin
    if current_user.is_superadmin:
        congregations = Congregation.query.order_by(Congregation.name).all()
    elif current_user.is_church_admin:
        congregations = Congregation.query.filter_by(
            church_id=current_user.church_id
        ).order_by(Congregation.name).all()
    else:
        congregations = []

    # Escopo efetivo de congregações
    eff_cong_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_cong_ids = [congregation_id]

    # Anos disponíveis
    years = [r[0] for r in
             db.session.query(Trimester.year).distinct().order_by(Trimester.year.desc()).all()]

    # Trimestres (filtrados por ano)
    tq = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter)
    if year:
        tq = tq.filter_by(year=year)
    trimesters = tq.all()

    # Turmas respeitando congregação do usuário logado
    classes = Class.query.filter(
        Class.congregation_id.in_(eff_cong_ids)
    ).order_by(Class.name).all()

    # Títulos de lições únicos (filtrados pelo scope e turma)
    class_ids_for_lesson = [c.id for c in classes]
    lq = db.session.query(Lesson.title).distinct()
    if class_ids_for_lesson:
        lq = lq.filter(Lesson.class_id.in_(class_ids_for_lesson))
    else:
        lq = lq.filter(db.false())
    if trimester_id:
        lq = lq.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids:
            lq = lq.filter(Lesson.trimester_id.in_(t_ids))
    if class_id:
        lq = lq.filter(Lesson.class_id == class_id)
    lesson_titles = sorted([r[0] for r in lq.all() if r[0]], key=_natural_sort_key)

    # ── Filtrar lições ────────────────────────────────────────────────────
    all_class_ids = [c.id for c in classes]
    q = Lesson.query.filter(Lesson.class_id.in_(all_class_ids)) if all_class_ids else Lesson.query.filter(db.false())
    if trimester_id:
        q = q.filter_by(trimester_id=trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids:
            q = q.filter(Lesson.trimester_id.in_(t_ids))
    if class_id:
        q = q.filter_by(class_id=class_id)
    if lesson_title:
        q = q.filter(Lesson.title == lesson_title)
    lessons    = q.order_by(Lesson.date).all()
    lesson_ids = [l.id for l in lessons]

    # ── Stats por turma ───────────────────────────────────────────────────
    class_stats = []
    for c in classes:
        cls_ids = [l.id for l in lessons if l.class_id == c.id]
        if not cls_ids:
            continue
        enrolled  = _enrolled_count(c.id)
        present   = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == True).count()
        absent    = max(enrolled - present, 0)
        pct       = round((present / enrolled) * 100, 1) if enrolled > 0 else 0.0
        visitors  = Visitor.query.filter(Visitor.lesson_id.in_(cls_ids)).count()
        offering  = db.session.query(func.sum(Lesson.offering)).filter(Lesson.id.in_(cls_ids)).scalar() or 0.0
        bibles    = db.session.query(func.sum(Lesson.bibles)).filter(Lesson.id.in_(cls_ids)).scalar() or 0
        magazines = db.session.query(func.sum(Lesson.magazines)).filter(Lesson.id.in_(cls_ids)).scalar() or 0
        class_stats.append({
            'name': c.name, 'enrolled': enrolled,
            'present': present, 'absent': absent,
            'visitors': visitors, 'total_geral': present + visitors,
            'pct': pct, 'offering': offering,
            'bibles': bibles, 'magazines': magazines,
        })

    total_enrolled  = sum(s['enrolled']    for s in class_stats)
    total_present   = sum(s['present']     for s in class_stats)
    total_absent    = sum(s['absent']      for s in class_stats)
    total_visitors  = sum(s['visitors']    for s in class_stats)
    total_geral     = sum(s['total_geral'] for s in class_stats)
    total_offering  = sum(s['offering']    for s in class_stats)
    total_bibles    = sum(s['bibles']      for s in class_stats)
    total_magazines = sum(s['magazines']   for s in class_stats)
    total_pct       = round((total_present / total_enrolled) * 100, 1) if total_enrolled > 0 else 0.0

    # ── Dados para o gráfico ──────────────────────────────────────────────
    chart_labels = []
    chart_data   = []
    if lesson_ids:
        from collections import defaultdict
        by_date = defaultdict(lambda: {'present': 0, 'enrolled': 0})
        for l in lessons:
            c_enrolled = _enrolled_count(l.class_id)
            c_present  = Attendance.query.filter_by(lesson_id=l.id, present=True).count()
            key = l.date.strftime('%d/%m')
            by_date[key]['present']  += c_present
            by_date[key]['enrolled'] += c_enrolled
        for label in sorted(by_date.keys(), key=lambda d: (d[3:], d[:2])):
            v = by_date[label]
            pct = round((v['present'] / v['enrolled']) * 100, 1) if v['enrolled'] > 0 else 0
            chart_labels.append(label)
            chart_data.append(pct)

    # ── Aniversariantes do mês (respeitando scope) ────────────────────────
    today = date.today()
    month = today.month
    birthday_teachers = Teacher.query.filter(
        Teacher.congregation_id.in_(eff_cong_ids),
        func.extract('month', Teacher.birth_date) == month
    ).all()
    birthday_students = Student.query.filter(
        Student.congregation_id.in_(eff_cong_ids),
        func.extract('month', Student.birth_date) == month
    ).all()
    birthdays = (
        [{'name': t.name, 'type': 'Professor', 'birth_date': t.birth_date} for t in birthday_teachers] +
        [{'name': s.name, 'type': 'Aluno',     'birth_date': s.birth_date} for s in birthday_students]
    )
    birthdays.sort(key=lambda x: x['birth_date'].day if x['birth_date'] else 0)

    return render_template('dashboard/index.html',
        years=years, trimesters=trimesters, classes=classes,
        lesson_titles=lesson_titles, congregations=congregations,
        show_cong_filter=show_cong_filter,
        year=year, trimester_id=trimester_id, class_id=class_id,
        lesson_title=lesson_title, congregation_id=congregation_id,
        class_stats=class_stats,
        total_enrolled=total_enrolled, total_present=total_present,
        total_absent=total_absent, total_visitors=total_visitors,
        total_geral=total_geral, total_offering=total_offering,
        total_bibles=total_bibles, total_magazines=total_magazines,
        total_pct=total_pct,
        chart_labels=chart_labels, chart_data=chart_data,
        today=today, today_lessons=Lesson.query.filter_by(date=today).all(),
        birthdays=birthdays,
        total_students=Student.query.filter(Student.congregation_id.in_(eff_cong_ids)).count(),
        total_teachers=Teacher.query.filter(Teacher.congregation_id.in_(eff_cong_ids)).count(),
        total_classes=Class.query.filter(Class.congregation_id.in_(eff_cong_ids)).count(),
    )