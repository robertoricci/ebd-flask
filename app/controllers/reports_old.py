from flask import Blueprint, render_template, request, make_response
from flask_login import login_required
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.klass import Class
from app.models.trimester import Trimester
from app.utils.decorators import admin_required
from sqlalchemy import func
from datetime import datetime

reports_bp = Blueprint('reports', __name__, url_prefix='/relatorios')


def _get_filters():
    trimester_id = request.args.get('trimester_id', type=int)
    class_id     = request.args.get('class_id', type=int)
    lesson_id    = request.args.get('lesson_id', type=int)
    return trimester_id, class_id, lesson_id


def _build_stats(trimester_id, class_id, lesson_id):
    classes = Class.query.order_by(Class.name).all()

    q = Lesson.query
    if trimester_id:
        q = q.filter_by(trimester_id=trimester_id)
    if class_id:
        q = q.filter_by(class_id=class_id)
    if lesson_id:
        q = q.filter_by(id=lesson_id)

    lessons = q.all()

    class_stats = []
    for c in classes:
        cls_ids = [l.id for l in lessons if l.class_id == c.id]
        if not cls_ids:
            continue
        present        = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == True).count()
        absent         = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == False).count()
        total_att      = present + absent
        pct            = round((present / total_att) * 100, 1) if total_att > 0 else 0.0
        visitors_count = Visitor.query.filter(Visitor.lesson_id.in_(cls_ids)).count()
        offering       = db.session.query(func.sum(Lesson.offering)).filter(Lesson.id.in_(cls_ids)).scalar() or 0.0
        total_geral    = present + visitors_count
        class_stats.append({
            'name':        c.name,
            'lessons':     len(cls_ids),
            'present':     present,
            'absent':      absent,
            'visitors':    visitors_count,
            'total_geral': total_geral,
            'pct':         pct,
            'offering':    offering,
        })

    total_lessons  = sum(s['lessons']     for s in class_stats)
    total_present  = sum(s['present']     for s in class_stats)
    total_absent   = sum(s['absent']      for s in class_stats)
    total_visitors = sum(s['visitors']    for s in class_stats)
    total_geral    = sum(s['total_geral'] for s in class_stats)
    total_offering = sum(s['offering']    for s in class_stats)
    denom          = total_present + total_absent
    total_pct      = round((total_present / denom) * 100, 1) if denom > 0 else 0.0

    return (class_stats, total_lessons, total_present, total_absent,
            total_visitors, total_geral, total_pct, total_offering)


@reports_bp.route('/')
@login_required
@admin_required
def index():
    trimesters = Trimester.query.order_by(Trimester.year.desc()).all()
    classes    = Class.query.order_by(Class.name).all()

    trimester_id, class_id, lesson_id = _get_filters()

    lq = Lesson.query.order_by(Lesson.date.desc())
    if trimester_id:
        lq = lq.filter_by(trimester_id=trimester_id)
    if class_id:
        lq = lq.filter_by(class_id=class_id)
    available_lessons = lq.all()

    (class_stats, total_lessons, total_present, total_absent,
     total_visitors, total_geral, total_pct, total_offering) = _build_stats(trimester_id, class_id, lesson_id)

    return render_template('reports/index.html',
        trimesters=trimesters,
        classes=classes,
        available_lessons=available_lessons,
        trimester_id=trimester_id,
        class_id=class_id,
        lesson_id=lesson_id,
        class_stats=class_stats,
        total_lessons=total_lessons,
        total_present=total_present,
        total_absent=total_absent,
        total_visitors=total_visitors,
        total_geral=total_geral,
        total_pct=total_pct,
        total_offering=total_offering,
    )


@reports_bp.route('/pdf')
@login_required
@admin_required
def pdf():
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        return "Erro: reportlab não instalado. Rode: pip install reportlab", 500

    import io

    trimester_id, class_id, lesson_id = _get_filters()

    (class_stats, total_lessons, total_present, total_absent,
     total_visitors, total_geral, total_pct, total_offering) = _build_stats(trimester_id, class_id, lesson_id)

    labels = []
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: labels.append(t.name)
    if class_id:
        c = Class.query.get(class_id)
        if c: labels.append(c.name)
    if lesson_id:
        l = Lesson.query.get(lesson_id)
        if l: labels.append(l.title)
    filtro_label = ' · '.join(labels) if labels else 'Todos os dados'

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    BG_DARK = colors.HexColor('#0f1623')
    BG_CARD = colors.HexColor('#151d2e')
    ACCENT  = colors.HexColor('#2d9cdb')
    GREEN   = colors.HexColor('#10b981')
    RED     = colors.HexColor('#ef4444')
    MUTED   = colors.HexColor('#64748b')
    WHITE   = colors.white
    YELLOW  = colors.HexColor('#f59e0b')

    def pct_color(v):
        if v >= 75: return GREEN
        if v >= 50: return YELLOW
        return RED

    def fmt_currency(v):
        return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    title_style = ParagraphStyle('title', fontSize=18, textColor=ACCENT,
                                 fontName='Helvetica-Bold', spaceAfter=4)
    sub_style   = ParagraphStyle('sub',   fontSize=9,  textColor=MUTED,
                                 fontName='Helvetica',  spaceAfter=14)

    story = []
    story.append(Paragraph('EBD - Relatorio de Frequencia', title_style))
    story.append(Paragraph(
        f'Filtro: {filtro_label}    |    Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        sub_style
    ))

    # Tabela de detalhes
    headers = ['Turma', 'Aulas', 'Presentes', 'Ausentes', 'Visitantes', 'Total (P+V)', 'Frequencia', 'Oferta']
    rows = [headers]
    for s in class_stats:
        rows.append([
            s['name'],
            str(s['lessons']),
            str(s['present']),
            str(s['absent']),
            str(s['visitors']),
            str(s['total_geral']),
            f"{s['pct']}%",
            fmt_currency(s['offering']),
        ])
    rows.append([
        'TOTAL',
        str(total_lessons),
        str(total_present),
        str(total_absent),
        str(total_visitors),
        str(total_geral),
        f'{total_pct}%',
        fmt_currency(total_offering),
    ])

    col_widths = [5*cm, 2.2*cm, 2.8*cm, 2.8*cm, 2.8*cm, 3.2*cm, 2.8*cm, 3.5*cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)

    ts = TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  ACCENT),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  8),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN',         (0, 0), (0, -1),  'LEFT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#1e2d44')),
        ('ROWBACKGROUNDS',(0, 1), (-1, -2), [BG_DARK, BG_CARD]),
        ('TEXTCOLOR',     (0, 1), (-1, -2), WHITE),
        ('BACKGROUND',    (0, -1),(-1, -1), BG_CARD),
        ('TEXTCOLOR',     (0, -1),(-1, -1), WHITE),
        ('FONTNAME',      (0, -1),(-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE',     (0, -1),(-1, -1), 1.5, ACCENT),
    ])
    for i, s in enumerate(class_stats, start=1):
        ts.add('TEXTCOLOR', (2, i), (2, i), GREEN)
        ts.add('TEXTCOLOR', (3, i), (3, i), RED)
        ts.add('TEXTCOLOR', (6, i), (6, i), pct_color(s['pct']))

    total_row = len(rows) - 1
    ts.add('TEXTCOLOR', (2, total_row), (2, total_row), GREEN)
    ts.add('TEXTCOLOR', (3, total_row), (3, total_row), RED)
    ts.add('TEXTCOLOR', (6, total_row), (6, total_row), pct_color(total_pct))

    t.setStyle(ts)
    story.append(t)

    doc.build(story)
    buf.seek(0)

    response = make_response(buf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=relatorio_ebd_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    return response
