from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app import db
from app.models.student import Student
from app.models.klass import Class
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.trimester import Trimester
from app.models.church import Congregation
from app.utils.decorators import admin_required
from app.utils.scope import scoped, congregation_ids
from sqlalchemy import func
from datetime import datetime

frequency_bp = Blueprint('frequency', __name__, url_prefix='/frequencias')


def _get_filters():
    year            = request.args.get('year',         type=int)
    trimester_id    = request.args.get('trimester_id', type=int)
    lesson_title    = request.args.get('lesson_title', '').strip()
    class_id        = request.args.get('class_id',     type=int)
    congregation_id = request.args.get('congregation_id', type=int)
    return year, trimester_id, lesson_title, class_id, congregation_id


def _visible_congregations():
    if current_user.is_superadmin:
        return Congregation.query.order_by(Congregation.name).all()
    if current_user.is_church_admin:
        return Congregation.query.filter_by(
            church_id=current_user.church_id
        ).order_by(Congregation.name).all()
    return []


def _build_frequency(year, trimester_id, lesson_title, class_id, congregation_id):
    """
    Retorna lista de dicts com frequência por aluno, já ordenada do maior para menor.
    """
    cong_ids = congregation_ids()

    # Filtrar congregação específica se escolhida
    eff_cong_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_cong_ids = [congregation_id]

    # Turmas do scope
    cq = Class.query.filter(Class.congregation_id.in_(eff_cong_ids))
    if class_id:
        cq = cq.filter(Class.id == class_id)
    classes = cq.all()
    class_ids = [c.id for c in classes]

    if not class_ids:
        return []

    # Lições filtradas
    lq = Lesson.query.filter(Lesson.class_id.in_(class_ids))
    if trimester_id:
        lq = lq.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        lq = lq.filter(Lesson.trimester_id.in_(t_ids)) if t_ids else lq.filter(db.false())
    if lesson_title:
        lq = lq.filter(Lesson.title == lesson_title)

    lesson_ids = [l.id for l in lq.all()]
    if not lesson_ids:
        return []

    total_lessons = len(lesson_ids)

    # Total de presenças por aluno usando query agregada
    freq_rows = (
        db.session.query(
            Student.id,
            Student.name,
            Student.email,
            Student.phone,
            func.count(Attendance.id).label('presences')
        )
        .join(Attendance, Attendance.student_id == Student.id)
        .filter(
            Attendance.lesson_id.in_(lesson_ids),
            Attendance.present == True
        )
        .filter(Student.congregation_id.in_(eff_cong_ids))
        .group_by(Student.id, Student.name, Student.email, Student.phone)
        .order_by(func.count(Attendance.id).desc())
        .all()
    )

    # Também incluir alunos matriculados com 0 presenças
    enrolled_ids = set()
    class_by_student = {}  # student_id → lista de turmas
    for c in classes:
        for s in c.students:
            enrolled_ids.add(s.id)
            class_by_student.setdefault(s.id, []).append(c.name)

    freq_dict = {row.id: row for row in freq_rows}
    result = []

    for row in freq_rows:
        turmas = class_by_student.get(row.id, ['—'])
        pct    = round((row.presences / total_lessons) * 100, 1) if total_lessons > 0 else 0
        result.append({
            'id':        row.id,
            'name':      row.name,
            'email':     row.email or '—',
            'phone':     row.phone or '—',
            'classes':   ', '.join(turmas),
            'presences': row.presences,
            'total':     total_lessons,
            'pct':       pct,
        })

    # Alunos com 0 presenças
    for sid in enrolled_ids:
        if sid not in freq_dict:
            s = Student.query.get(sid)
            if not s: continue
            turmas = class_by_student.get(sid, ['—'])
            result.append({
                'id':        s.id,
                'name':      s.name,
                'email':     s.email or '—',
                'phone':     s.phone or '—',
                'classes':   ', '.join(turmas),
                'presences': 0,
                'total':     total_lessons,
                'pct':       0.0,
            })

    # Reordenar: mais presenças primeiro
    result.sort(key=lambda x: x['presences'], reverse=True)
    return result


@frequency_bp.route('/')
@login_required
@admin_required
def index():
    year, trimester_id, lesson_title, class_id, congregation_id = _get_filters()

    cong_ids = congregation_ids()

    # Anos
    years = [r[0] for r in
             db.session.query(Trimester.year).distinct().order_by(Trimester.year.desc()).all()]

    # Trimestres (filtrado por ano)
    tq = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter)
    if year: tq = tq.filter_by(year=year)
    trimesters     = tq.all()
    all_trimesters = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter).all()

    # Turmas do scope
    eff_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_ids = [congregation_id]
    classes = Class.query.filter(Class.congregation_id.in_(eff_ids)).order_by(Class.name).all()

    # Títulos de lições disponíveis
    lq = db.session.query(Lesson.title).distinct()
    cids = [c.id for c in classes]
    if cids:
        lq = lq.filter(Lesson.class_id.in_(cids))
    if trimester_id:
        lq = lq.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids: lq = lq.filter(Lesson.trimester_id.in_(t_ids))
    lesson_titles = sorted([r[0] for r in lq.all() if r[0]])

    # Congregações para filtro (só superadmin / church_admin)
    congregations = _visible_congregations()

    # Dados
    frequency = _build_frequency(year, trimester_id, lesson_title, class_id, congregation_id)

    return render_template('frequency/index.html',
        years=years, trimesters=trimesters, all_trimesters=all_trimesters,
        classes=classes, lesson_titles=lesson_titles, congregations=congregations,
        year=year, trimester_id=trimester_id, lesson_title=lesson_title,
        class_id=class_id, congregation_id=congregation_id,
        frequency=frequency)


@frequency_bp.route('/pdf')
@login_required
@admin_required
def pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer, HRFlowable)
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        return "Erro: instale reportlab", 500

    import io
    from app.models.church import Church

    year, trimester_id, lesson_title, class_id, congregation_id = _get_filters()
    frequency = _build_frequency(year, trimester_id, lesson_title, class_id, congregation_id)
    cong_ids  = congregation_ids()

    # ── Cores ──────────────────────────────────────────────────────────────
    C_BG     = colors.HexColor('#0f1623')
    C_CARD   = colors.HexColor('#151d2e')
    C_CARD2  = colors.HexColor('#1a2438')
    C_HEAD   = colors.HexColor('#2d9cdb')
    C_BORDER = colors.HexColor('#1e2d44')
    C_GREEN  = colors.HexColor('#10b981')
    C_RED    = colors.HexColor('#ef4444')
    C_YELLOW = colors.HexColor('#f59e0b')
    C_MUTED  = colors.HexColor('#94a3b8')
    C_WHITE  = colors.white

    def pct_col(v):
        if v >= 75: return C_GREEN
        if v >= 50: return C_YELLOW
        return C_RED

    # ── Identificação ──────────────────────────────────────────────────────
    pdf_church_name = '—'
    pdf_cong_name   = '—'
    if current_user.congregation and current_user.congregation.church:
        pdf_church_name = current_user.congregation.church.name
        pdf_cong_name   = current_user.congregation.name
    elif current_user.church:
        pdf_church_name = current_user.church.name
    if current_user.is_superadmin:
        if congregation_id:
            cg = Congregation.query.get(congregation_id)
            if cg:
                pdf_cong_name = cg.name
                ch = Church.query.get(cg.church_id)
                if ch: pdf_church_name = ch.name
        else:
            pdf_church_name = 'Todas'
            pdf_cong_name   = 'Todas'

    pdf_trimester = '—'
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: pdf_trimester = t.name
    elif year:
        pdf_trimester = 'Todos'

    pdf_class = '—'
    if class_id:
        c = Class.query.get(class_id)
        if c: pdf_class = c.name
    else:
        pdf_class = 'Todas'

    # ── Estilos ────────────────────────────────────────────────────────────
    sT   = ParagraphStyle('T',  fontSize=18, textColor=C_HEAD,  fontName='Helvetica-Bold', spaceAfter=2)
    sSub = ParagraphStyle('Su', fontSize=8,  textColor=C_MUTED, fontName='Helvetica',      spaceAfter=4)
    sFt  = ParagraphStyle('Ft', fontSize=7,  textColor=C_MUTED, fontName='Helvetica',      alignment=TA_CENTER, spaceBefore=6)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm,  bottomMargin=1.5*cm)
    story = []
    page_w = A4[0] - 3*cm

    # Título
    story.append(Paragraph('EBD – Frequencia de Alunos', sT))
    story.append(Paragraph(
        f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}  |  Por: {current_user.name}',
        sSub))

    # Bloco de identificação
    ic = ParagraphStyle('ic', fontSize=8, textColor=C_WHITE, fontName='Helvetica', leading=13)
    id_data = [[
        Paragraph(f'<b>Igreja</b><br/>{pdf_church_name}',    ic),
        Paragraph(f'<b>Congregacao</b><br/>{pdf_cong_name}', ic),
        Paragraph(f'<b>Ano</b><br/>{str(year) if year else "Todos"}', ic),
        Paragraph(f'<b>Trimestre</b><br/>{pdf_trimester}',   ic),
        Paragraph(f'<b>Turma</b><br/>{pdf_class}',           ic),
        Paragraph(f'<b>Licao</b><br/>{lesson_title if lesson_title else "Todas"}', ic),
    ]]
    id_cw = [page_w*0.20, page_w*0.18, page_w*0.08, page_w*0.20, page_w*0.18, page_w*0.16]
    id_t  = Table(id_data, colWidths=id_cw)
    id_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), C_CARD2),
        ('GRID',          (0,0), (-1,-1), .4,     C_BORDER),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE',     (0,0), (-1,0),  2,      C_HEAD),
    ]))
    story.append(id_t)
    story.append(Spacer(1, .4*cm))

    # Tabela principal
    if not frequency:
        story.append(Paragraph('Nenhum dado encontrado para os filtros selecionados.',
                                ParagraphStyle('e', fontSize=9, textColor=C_MUTED)))
    else:
        headers = ['#', 'Nome', 'Turma(s)', 'Telefone', 'Email', 'Presenças', 'Total', '%']
        cw = [page_w*0.04, page_w*0.20, page_w*0.17, page_w*0.12,
              page_w*0.24, page_w*0.08, page_w*0.07, page_w*0.08]

        rows = [headers]
        for i, r in enumerate(frequency, 1):
            rows.append([
                str(i),
                r['name'],
                r['classes'],
                r['phone'],
                r['email'],
                str(r['presences']),
                str(r['total']),
                f"{r['pct']}%",
            ])

        t = Table(rows, colWidths=cw, repeatRows=1)
        ts = TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),  C_HEAD),
            ('TEXTCOLOR',     (0,0),  (-1,0),  C_WHITE),
            ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),  (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1),  (-1,-1), [C_BG, C_CARD]),
            ('TEXTCOLOR',     (0,1),  (-1,-1), C_WHITE),
            ('ALIGN',         (0,0),  (0,-1),  'CENTER'),
            ('ALIGN',         (5,0),  (-1,-1), 'CENTER'),
            ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),  (-1,-1), 6),
            ('BOTTOMPADDING', (0,0),  (-1,-1), 6),
            ('LEFTPADDING',   (0,0),  (-1,-1), 6),
            ('GRID',          (0,0),  (-1,-1), .3, C_BORDER),
        ])
        # Colorir coluna de %
        for i, r in enumerate(frequency, 1):
            col = pct_col(r['pct'])
            ts.add('TEXTCOLOR', (7, i), (7, i), col)
            ts.add('FONTNAME',  (7, i), (7, i), 'Helvetica-Bold')
            ts.add('TEXTCOLOR', (5, i), (5, i), C_GREEN)
        t.setStyle(ts)
        story.append(t)

    # Rodapé
    story.append(Spacer(1, .4*cm))
    story.append(HRFlowable(width='100%', thickness=.5, color=C_BORDER))
    story.append(Paragraph(
        f'EBD – Frequencia de Alunos  ·  {datetime.now().strftime("%d/%m/%Y %H:%M")}  ·  {len(frequency)} aluno(s)',
        sFt))

    doc.build(story)
    buf.seek(0)
    fname = f'frequencia_alunos_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp  = make_response(buf.read())
    resp.headers['Content-Type']        = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp
