from flask import Blueprint, render_template, request, make_response
from flask_login import login_required
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.klass import Class
from app.models.trimester import Trimester
from app.models.student import class_students
from app.utils.decorators import admin_required
from sqlalchemy import func, select
from datetime import datetime
import re

reports_bp = Blueprint('reports', __name__, url_prefix='/relatorios')


def _natural_sort_key(s):
    """Ordena strings com números de forma natural: Lição 1, Lição 2 ... Lição 10"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s or '')]


def _get_filters():
    trimester_id  = request.args.get('trimester_id', type=int)
    class_id      = request.args.get('class_id', type=int)
    lesson_title  = request.args.get('lesson_title', '').strip()
    return trimester_id, class_id, lesson_title


def _get_unique_lesson_titles(trimester_id=None, class_id=None):
    """Retorna títulos únicos de lições ordenados numericamente."""
    q = db.session.query(Lesson.title).distinct()
    if trimester_id:
        q = q.filter(Lesson.trimester_id == trimester_id)
    if class_id:
        q = q.filter(Lesson.class_id == class_id)
    titles = [row[0] for row in q.all() if row[0]]
    titles.sort(key=_natural_sort_key)
    return titles


def _enrolled_count(class_id):
    """Conta alunos matriculados via query direta, evitando problemas de lazy load."""
    return db.session.execute(
        select(func.count()).select_from(class_students).where(
            class_students.c.class_id == class_id
        )
    ).scalar() or 0


def _build_stats(trimester_id, class_id, lesson_title):
    classes = Class.query.order_by(Class.name).all()

    q = Lesson.query
    if trimester_id:
        q = q.filter_by(trimester_id=trimester_id)
    if class_id:
        q = q.filter_by(class_id=class_id)
    if lesson_title:
        q = q.filter(Lesson.title == lesson_title)

    lessons = q.all()

    class_stats = []
    for c in classes:
        cls_ids = [l.id for l in lessons if l.class_id == c.id]
        if not cls_ids:
            continue

        enrolled       = _enrolled_count(c.id)
        present        = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == True).count()
        absent         = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == False).count()
        total_att      = present + absent
        pct            = round((present / total_att) * 100, 1) if total_att > 0 else 0.0
        visitors_count = Visitor.query.filter(Visitor.lesson_id.in_(cls_ids)).count()
        offering       = db.session.query(func.sum(Lesson.offering)).filter(Lesson.id.in_(cls_ids)).scalar() or 0.0
        total_geral    = present + visitors_count

        class_stats.append({
            'name':        c.name,
            'enrolled':    enrolled,
            'lessons':     len(cls_ids),
            'present':     present,
            'absent':      absent,
            'visitors':    visitors_count,
            'total_geral': total_geral,
            'pct':         pct,
            'offering':    offering,
        })

    total_enrolled = sum(s['enrolled']    for s in class_stats)
    total_lessons  = sum(s['lessons']     for s in class_stats)
    total_present  = sum(s['present']     for s in class_stats)
    total_absent   = sum(s['absent']      for s in class_stats)
    total_visitors = sum(s['visitors']    for s in class_stats)
    total_geral    = sum(s['total_geral'] for s in class_stats)
    total_offering = sum(s['offering']    for s in class_stats)
    denom          = total_present + total_absent
    total_pct      = round((total_present / denom) * 100, 1) if denom > 0 else 0.0

    return (class_stats, total_enrolled, total_lessons, total_present, total_absent,
            total_visitors, total_geral, total_pct, total_offering)


@reports_bp.route('/')
@login_required
@admin_required
def index():
    trimesters    = Trimester.query.order_by(Trimester.year.desc()).all()
    classes       = Class.query.order_by(Class.name).all()
    trimester_id, class_id, lesson_title = _get_filters()
    lesson_titles = _get_unique_lesson_titles(trimester_id, class_id)

    (class_stats, total_enrolled, total_lessons, total_present, total_absent,
     total_visitors, total_geral, total_pct, total_offering) = _build_stats(trimester_id, class_id, lesson_title)

    filter_labels = []
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: filter_labels.append(('Trimestre', t.name))
    if class_id:
        c = Class.query.get(class_id)
        if c: filter_labels.append(('Turma', c.name))
    if lesson_title:
        filter_labels.append(('Licao', lesson_title))

    return render_template('reports/index.html',
        trimesters=trimesters, classes=classes,
        lesson_titles=lesson_titles,
        trimester_id=trimester_id, class_id=class_id, lesson_title=lesson_title,
        filter_labels=filter_labels,
        class_stats=class_stats,
        total_enrolled=total_enrolled, total_lessons=total_lessons,
        total_present=total_present, total_absent=total_absent,
        total_visitors=total_visitors, total_geral=total_geral,
        total_pct=total_pct, total_offering=total_offering,
    )


# ─── PDF ────────────────────────────────────────────────────────────────────

def _fmt_cur(v):
    return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def _pct_label(v):
    return ('>=75%' if v >= 75 else ('>=50%' if v >= 50 else '<50%'))


@reports_bp.route('/pdf')
@login_required
@admin_required
def pdf():
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer, HRFlowable)
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        return "Erro: instale reportlab (pip install reportlab)", 500

    import io

    trimester_id, class_id, lesson_title = _get_filters()

    (class_stats, total_enrolled, total_lessons, total_present, total_absent,
     total_visitors, total_geral, total_pct, total_offering) = _build_stats(trimester_id, class_id, lesson_title)

    # labels de filtro
    filter_parts = []
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: filter_parts.append(f'Trimestre: {t.name}')
    if class_id:
        c = Class.query.get(class_id)
        if c: filter_parts.append(f'Turma: {c.name}')
    if lesson_title:
        filter_parts.append(f'Licao: {lesson_title}')

    # ── Paleta ──────────────────────────────────────────────────────────────
    C_BG     = colors.HexColor('#0f1623')
    C_CARD   = colors.HexColor('#151d2e')
    C_CARD2  = colors.HexColor('#1a2438')
    C_HEAD   = colors.HexColor('#2d9cdb')
    C_BORDER = colors.HexColor('#1e2d44')
    C_GREEN  = colors.HexColor('#10b981')
    C_RED    = colors.HexColor('#ef4444')
    C_YELLOW = colors.HexColor('#f59e0b')
    C_BLUE   = colors.HexColor('#2d9cdb')
    C_MUTED  = colors.HexColor('#94a3b8')
    C_WHITE  = colors.white

    def pct_col(v):
        if v >= 75: return C_GREEN
        if v >= 50: return C_YELLOW
        return C_RED

    # ── Estilos ──────────────────────────────────────────────────────────────
    sTitle  = ParagraphStyle('sT', fontSize=18, textColor=C_HEAD,
                              fontName='Helvetica-Bold', spaceAfter=3)
    sSub    = ParagraphStyle('sS', fontSize=8, textColor=C_MUTED,
                              fontName='Helvetica', spaceAfter=6)
    sFilter = ParagraphStyle('sF', fontSize=8, textColor=C_WHITE,
                              fontName='Helvetica-Bold', spaceAfter=12,
                              backColor=C_CARD2, borderPad=5,
                              leftIndent=4, rightIndent=4)
    sSec    = ParagraphStyle('sSc', fontSize=9, textColor=C_MUTED,
                              fontName='Helvetica-Bold', spaceAfter=6,
                              spaceBefore=10, textTransform='uppercase',
                              letterSpacing=1)
    sFooter = ParagraphStyle('sFt', fontSize=7, textColor=C_MUTED,
                              fontName='Helvetica', alignment=TA_CENTER, spaceBefore=4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []

    # ── 1. Cabeçalho ─────────────────────────────────────────────────────────
    story.append(Paragraph('EBD - Relatorio de Frequencia', sTitle))
    story.append(Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}', sSub))

    if filter_parts:
        story.append(Paragraph('Filtros:  ' + '    |    '.join(filter_parts), sFilter))
    else:
        story.append(Paragraph('Filtros: Todos os dados', sFilter))

    # ── 2. Cards de resumo ────────────────────────────────────────────────────
    story.append(Paragraph('Resumo Geral', sSec))

    summary_labels = ['Matriculados', 'Aulas', 'Presentes', 'Ausentes',
                      'Visitantes', 'Total (P+V)', 'Frequencia', 'Oferta Total']
    summary_values = [
        str(total_enrolled),
        str(total_lessons),
        str(total_present),
        str(total_absent),
        str(total_visitors),
        str(total_geral),
        f'{total_pct}%',
        _fmt_cur(total_offering),
    ]
    summary_colors = [
        C_BLUE, C_YELLOW, C_GREEN, C_RED,
        colors.HexColor('#8b5cf6'), C_BLUE, pct_col(total_pct), C_GREEN,
    ]

    sum_rows = [summary_labels, summary_values]
    cw8 = [3.1*cm] * 8
    sum_t = Table(sum_rows, colWidths=cw8)
    sum_style = TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), C_CARD),
        ('BACKGROUND',    (0,1), (-1,1), C_BG),
        ('TEXTCOLOR',     (0,0), (-1,0), C_MUTED),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,0), 7),
        ('FONTNAME',      (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,1), (-1,1), 15),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.5, C_BORDER),
    ])
    for i, col in enumerate(summary_colors):
        sum_style.add('TEXTCOLOR', (i,1), (i,1), col)
    sum_t.setStyle(sum_style)
    story.append(sum_t)

    # ── 3. Barras de frequência ───────────────────────────────────────────────
    if class_stats:
        story.append(Paragraph('Frequencia por Turma', sSec))

        bar_data = []
        for s in class_stats:
            pct = s['pct']
            col = pct_col(pct)
            bar_data.append([
                Paragraph(s['name'],
                          ParagraphStyle('bn', textColor=C_WHITE, fontSize=8,
                                         fontName='Helvetica-Bold')),
                Paragraph(f'{pct}%',
                          ParagraphStyle('bp', textColor=col, fontSize=9,
                                         fontName='Helvetica-Bold', alignment=TA_RIGHT)),
            ])

        bar_t = Table(bar_data, colWidths=[22*cm, 2.5*cm])
        bar_ts = TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), C_CARD),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (0,-1),  8),
            ('RIGHTPADDING',  (1,0), (1,-1),  8),
            ('LINEBELOW',     (0,0), (-1,-2), 0.3, C_BORDER),
        ])
        # zebra leve
        for i in range(0, len(bar_data), 2):
            bar_ts.add('BACKGROUND', (0,i), (-1,i), C_CARD2)
        bar_t.setStyle(bar_ts)
        story.append(bar_t)

    # ── 4. Tabela detalhada ───────────────────────────────────────────────────
    story.append(Paragraph('Detalhamento por Turma', sSec))

    headers = ['Turma', 'Matriculados', 'Aulas', 'Presentes', 'Ausentes',
               'Visitantes', 'Total P+V', 'Frequencia', 'Oferta']
    det_rows = [headers]
    for s in class_stats:
        det_rows.append([
            s['name'],
            str(s['enrolled']),
            str(s['lessons']),
            str(s['present']),
            str(s['absent']),
            str(s['visitors']),
            str(s['total_geral']),
            f"{s['pct']}%",
            _fmt_cur(s['offering']),
        ])
    # linha TOTAL
    det_rows.append([
        'TOTAL',
        str(total_enrolled),
        str(total_lessons),
        str(total_present),
        str(total_absent),
        str(total_visitors),
        str(total_geral),
        f'{total_pct}%',
        _fmt_cur(total_offering),
    ])

    cw9 = [4.2*cm, 2.4*cm, 1.8*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2.6*cm, 2.4*cm, 3*cm]
    det_t = Table(det_rows, colWidths=cw9, repeatRows=1)
    det_ts = TableStyle([
        # Cabeçalho
        ('BACKGROUND',    (0,0),  (-1,0),  C_HEAD),
        ('TEXTCOLOR',     (0,0),  (-1,0),  C_WHITE),
        ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),  (-1,0),  8),
        # Dados
        ('ROWBACKGROUNDS',(0,1),  (-1,-2), [C_BG, C_CARD]),
        ('TEXTCOLOR',     (0,1),  (-1,-2), C_WHITE),
        ('FONTNAME',      (0,1),  (-1,-2), 'Helvetica'),
        ('FONTSIZE',      (0,1),  (-1,-2), 8),
        # Linha total
        ('BACKGROUND',    (0,-1), (-1,-1), C_CARD2),
        ('TEXTCOLOR',     (0,-1), (-1,-1), C_WHITE),
        ('FONTNAME',      (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('LINEABOVE',     (0,-1), (-1,-1), 1.5, C_HEAD),
        # Layout
        ('ALIGN',         (0,0),  (-1,-1), 'CENTER'),
        ('ALIGN',         (0,1),  (0,-1),  'LEFT'),
        ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),  (-1,-1), 7),
        ('BOTTOMPADDING', (0,0),  (-1,-1), 7),
        ('LEFTPADDING',   (0,1),  (0,-1),  8),
        ('GRID',          (0,0),  (-1,-1), 0.4, C_BORDER),
    ])
    # Cores por linha
    for i, s in enumerate(class_stats, start=1):
        det_ts.add('TEXTCOLOR', (3,i), (3,i), C_GREEN)
        det_ts.add('TEXTCOLOR', (4,i), (4,i), C_RED)
        det_ts.add('TEXTCOLOR', (7,i), (7,i), pct_col(s['pct']))
    tr = len(det_rows) - 1
    det_ts.add('TEXTCOLOR', (3,tr), (3,tr), C_GREEN)
    det_ts.add('TEXTCOLOR', (4,tr), (4,tr), C_RED)
    det_ts.add('TEXTCOLOR', (7,tr), (7,tr), pct_col(total_pct))
    det_t.setStyle(det_ts)
    story.append(det_t)

    # ── 5. Rodapé ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=C_BORDER))
    story.append(Paragraph(
        f'EBD Frequencia  -  Relatorio gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        sFooter
    ))

    doc.build(story)
    buf.seek(0)

    fname = f'relatorio_ebd_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp