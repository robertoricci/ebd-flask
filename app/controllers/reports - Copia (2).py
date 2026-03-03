from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.klass import Class
from app.models.trimester import Trimester
from app.models.student import class_students
from app.models.church import Congregation
from app.utils.decorators import admin_required
from app.utils.scope import scoped, scoped_class_ids, congregation_ids
from sqlalchemy import func, select
from datetime import datetime
import re

reports_bp = Blueprint('reports', __name__, url_prefix='/relatorios')


def _natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s or '')]


def _get_filters():
    year            = request.args.get('year',            type=int)
    trimester_id    = request.args.get('trimester_id',    type=int)
    lesson_title    = request.args.get('lesson_title',    '').strip()
    class_id        = request.args.get('class_id',        type=int)
    congregation_id = request.args.get('congregation_id', type=int)
    return year, trimester_id, lesson_title, class_id, congregation_id


def _get_years():
    rows = db.session.query(Trimester.year).distinct().order_by(Trimester.year.desc()).all()
    return [r[0] for r in rows]


def _get_unique_lesson_titles(year=None, trimester_id=None, class_id=None, cong_ids=None):
    """Retorna títulos de lições com status FINALIZADO."""
    q = db.session.query(Lesson.title).distinct().filter(Lesson.status == 'FINALIZADO')
    if cong_ids:
        class_ids = [c.id for c in Class.query.filter(Class.congregation_id.in_(cong_ids)).all()]
        q = q.filter(Lesson.class_id.in_(class_ids))
    if trimester_id:
        q = q.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids: q = q.filter(Lesson.trimester_id.in_(t_ids))
    if class_id:
        q = q.filter(Lesson.class_id == class_id)
    titles = [row[0] for row in q.all() if row[0]]
    titles.sort(key=_natural_sort_key)
    return titles


def _enrolled_count(class_id):
    return db.session.execute(
        select(func.count()).select_from(class_students).where(
            class_students.c.class_id == class_id
        )
    ).scalar() or 0


def _build_stats(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids):
    cq = Class.query.filter(Class.congregation_id.in_(cong_ids))
    if congregation_id and congregation_id in cong_ids:
        cq = cq.filter(Class.congregation_id == congregation_id)
    if class_id:
        cq = cq.filter(Class.id == class_id)
    classes = cq.order_by(Class.name).all()

    all_class_ids = [c.id for c in classes]
    lq = Lesson.query.filter(Lesson.class_id.in_(all_class_ids)) if all_class_ids else Lesson.query.filter(db.false())
    if trimester_id:
        lq = lq.filter_by(trimester_id=trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids: lq = lq.filter(Lesson.trimester_id.in_(t_ids))
    if lesson_title:
        lq = lq.filter(Lesson.title == lesson_title)
    lessons = lq.all()

    class_stats = []
    for c in classes:
        cls_ids = [l.id for l in lessons if l.class_id == c.id]
        if not cls_ids: continue
        enrolled  = _enrolled_count(c.id)
        present   = Attendance.query.filter(Attendance.lesson_id.in_(cls_ids), Attendance.present == True).count()
        absent    = max(enrolled - present, 0)
        pct       = round((present / enrolled) * 100, 1) if enrolled > 0 else 0.0
        visitors  = Visitor.query.filter(Visitor.lesson_id.in_(cls_ids)).count()
        offering  = db.session.query(func.sum(Lesson.offering)).filter(Lesson.id.in_(cls_ids)).scalar() or 0.0
        bibles    = db.session.query(func.sum(Lesson.bibles)).filter(Lesson.id.in_(cls_ids)).scalar() or 0
        magazines = db.session.query(func.sum(Lesson.magazines)).filter(Lesson.id.in_(cls_ids)).scalar() or 0
        cong_name = c.congregation.name if c.congregation else '—'
        class_stats.append({'name': c.name, 'congregation': cong_name,
            'enrolled': enrolled, 'present': present, 'absent': absent,
            'visitors': visitors, 'total_geral': present + visitors,
            'pct': pct, 'offering': offering, 'bibles': bibles, 'magazines': magazines})

    te = sum(s['enrolled']    for s in class_stats)
    tp = sum(s['present']     for s in class_stats)
    ta = sum(s['absent']      for s in class_stats)
    tv = sum(s['visitors']    for s in class_stats)
    tg = sum(s['total_geral'] for s in class_stats)
    to = sum(s['offering']    for s in class_stats)
    tb = sum(s['bibles']      for s in class_stats)
    tm = sum(s['magazines']   for s in class_stats)
    tpct = round((tp / te) * 100, 1) if te > 0 else 0.0
    return class_stats, te, tp, ta, tv, tg, tpct, to, tb, tm


def _get_visitors_for_lesson(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids):
    """Retorna lista de visitantes filtrados — só quando lesson_title está selecionado."""
    if not lesson_title:
        return []

    eff_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_ids = [congregation_id]

    cq = Class.query.filter(Class.congregation_id.in_(eff_ids))
    if class_id:
        cq = cq.filter(Class.id == class_id)
    class_ids = [c.id for c in cq.all()]

    lq = Lesson.query.filter(
        Lesson.class_id.in_(class_ids),
        Lesson.title == lesson_title,
        Lesson.status == 'FINALIZADO'
    )
    if trimester_id:
        lq = lq.filter(Lesson.trimester_id == trimester_id)
    elif year:
        t_ids = [t.id for t in Trimester.query.filter_by(year=year).all()]
        if t_ids: lq = lq.filter(Lesson.trimester_id.in_(t_ids))

    lesson_ids = [l.id for l in lq.all()]
    if not lesson_ids:
        return []

    visitors = (Visitor.query
                .filter(Visitor.lesson_id.in_(lesson_ids))
                .order_by(Visitor.name)
                .all())
    return visitors


@reports_bp.route('/')
@login_required
@admin_required
def index():
    cong_ids = congregation_ids()
    years    = _get_years()
    year, trimester_id, lesson_title, class_id, congregation_id = _get_filters()

    tq = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter)
    if year: tq = tq.filter_by(year=year)
    trimesters = tq.all()

    if current_user.is_superadmin:
        congregations = Congregation.query.order_by(Congregation.name).all()
    elif current_user.is_church_admin:
        congregations = Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    else:
        congregations = []

    eff_cong_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_cong_ids = [congregation_id]

    cq = Class.query.filter(Class.congregation_id.in_(eff_cong_ids))
    classes = cq.order_by(Class.name).all()

    # Lições FINALIZADAS para o filtro (lição vem ANTES da turma)
    lesson_titles = _get_unique_lesson_titles(year, trimester_id, class_id, eff_cong_ids)

    # Dados só aparecem se lição selecionada
    show_data = bool(lesson_title)
    class_stats = te = tp = ta = tv = tg = tpct = to_ = tb = tm = None
    visitors_list = []

    if show_data:
        stats = _build_stats(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids)
        class_stats, te, tp, ta, tv, tg, tpct, to_, tb, tm = stats
        visitors_list = _get_visitors_for_lesson(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids)

    filter_labels = []
    if year:         filter_labels.append(('Ano', str(year)))
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: filter_labels.append(('Trimestre', t.name))
    if congregation_id:
        cg = Congregation.query.get(congregation_id)
        if cg: filter_labels.append(('Congregação', cg.name))
    if lesson_title: filter_labels.append(('Lição', lesson_title))
    if class_id:
        c = Class.query.get(class_id)
        if c: filter_labels.append(('Turma', c.name))

    show_congregation_col = current_user.is_superadmin or current_user.is_church_admin

    return render_template('reports/index.html',
        years=years, trimesters=trimesters, classes=classes,
        congregations=congregations, lesson_titles=lesson_titles,
        year=year, trimester_id=trimester_id, class_id=class_id,
        congregation_id=congregation_id, lesson_title=lesson_title,
        filter_labels=filter_labels, show_data=show_data,
        class_stats=class_stats or [],
        visitors_list=visitors_list,
        show_congregation_col=show_congregation_col,
        total_enrolled=te or 0, total_present=tp or 0, total_absent=ta or 0,
        total_visitors=tv or 0, total_geral=tg or 0, total_pct=tpct or 0.0,
        total_offering=to_ or 0.0, total_bibles=tb or 0, total_magazines=tm or 0)


def _fmt_cur(v):
    return f'R$ {v:,.2f}'.replace(',','X').replace('.',',').replace('X','.')


@reports_bp.route('/pdf')
@login_required
@admin_required
def pdf():
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    except ImportError:
        return "Erro: instale reportlab", 500
    import io
    cong_ids = congregation_ids()
    year, trimester_id, lesson_title, class_id, congregation_id = _get_filters()
    stats = _build_stats(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids)
    class_stats, te, tp, ta, tv, tg, tpct, to_, tb, tm = stats
    show_cong = current_user.is_superadmin or current_user.is_church_admin

    # Visitantes (só se lição selecionada)
    visitors_list = _get_visitors_for_lesson(year, trimester_id, lesson_title, class_id, congregation_id, cong_ids)

    # ── Resolver identificação ──────────────────────────────────────────
    from app.models.church import Church
    pdf_church_name = '—'
    pdf_cong_name   = '—'
    if current_user.congregation and current_user.congregation.church:
        pdf_church_name = current_user.congregation.church.name
        pdf_cong_name   = current_user.congregation.name
    elif current_user.church:
        pdf_church_name = current_user.church.name
    if current_user.is_superadmin:
        if congregation_id:
            cg_obj = Congregation.query.get(congregation_id)
            if cg_obj:
                pdf_cong_name = cg_obj.name
                ch_obj = Church.query.get(cg_obj.church_id)
                if ch_obj: pdf_church_name = ch_obj.name
        else:
            pdf_church_name = 'Todas as Igrejas'
            pdf_cong_name   = 'Todas as Congregações'

    pdf_trimester = '—'
    if trimester_id:
        t_obj = Trimester.query.get(trimester_id)
        if t_obj: pdf_trimester = t_obj.name
    elif year:
        pdf_trimester = 'Todos os trimestres'

    filter_parts = []
    if class_id:
        c_obj = Class.query.get(class_id)
        if c_obj: filter_parts.append(f'Turma: {c_obj.name}')

    C_BG=colors.HexColor('#0f1623'); C_CARD=colors.HexColor('#151d2e')
    C_CARD2=colors.HexColor('#1a2438'); C_HEAD=colors.HexColor('#2d9cdb')
    C_BORDER=colors.HexColor('#1e2d44'); C_GREEN=colors.HexColor('#10b981')
    C_RED=colors.HexColor('#ef4444'); C_YELLOW=colors.HexColor('#f59e0b')
    C_BLUE=colors.HexColor('#2d9cdb'); C_PURPLE=colors.HexColor('#8b5cf6')
    C_MUTED=colors.HexColor('#94a3b8'); C_WHITE=colors.white

    def pct_col(v):
        if v>=75: return C_GREEN
        if v>=50: return C_YELLOW
        return C_RED

    sT   = ParagraphStyle('sT',  fontSize=18, textColor=C_HEAD,  fontName='Helvetica-Bold', spaceAfter=2)
    sS   = ParagraphStyle('sS',  fontSize=8,  textColor=C_MUTED, fontName='Helvetica',      spaceAfter=4)
    sF   = ParagraphStyle('sF',  fontSize=8,  textColor=C_WHITE, fontName='Helvetica-Bold', spaceAfter=10, backColor=C_CARD2, borderPad=5, leftIndent=4)
    sSc  = ParagraphStyle('sSc', fontSize=9,  textColor=C_MUTED, fontName='Helvetica-Bold', spaceAfter=6,  spaceBefore=10)
    sFt  = ParagraphStyle('sFt', fontSize=7,  textColor=C_MUTED, fontName='Helvetica',      alignment=TA_CENTER, spaceBefore=4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm,  bottomMargin=1.5*cm)
    story = []
    page_w = landscape(A4)[0] - 3*cm

    # Título
    story.append(Paragraph('EBD - Relatorio de Frequencia', sT))
    story.append(Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}  |  Por: {current_user.name}', sS))

    # Bloco de identificação
    ic = ParagraphStyle('ic', fontSize=8, textColor=C_WHITE, fontName='Helvetica', leading=12)
    id_data = [[
        Paragraph(f'<b>Igreja</b><br/>{pdf_church_name}',    ic),
        Paragraph(f'<b>Congregacao</b><br/>{pdf_cong_name}', ic),
        Paragraph(f'<b>Ano</b><br/>{str(year) if year else "Todos"}', ic),
        Paragraph(f'<b>Trimestre</b><br/>{pdf_trimester}',   ic),
        Paragraph(f'<b>Licao</b><br/>{lesson_title if lesson_title else "Todas"}', ic),
    ]]
    id_cw = [page_w*0.22, page_w*0.22, page_w*0.10, page_w*0.24, page_w*0.22]
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

    if filter_parts:
        story.append(Paragraph(f'Filtros adicionais: {"  |  ".join(filter_parts)}', sF))
    else:
        story.append(Spacer(1, .3*cm))

    # ── Cards resumo ────────────────────────────────────────────────────
    story.append(Paragraph('Resumo Geral', sSc))
    sl = ['Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Frequencia']
    sv = [str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%']
    sc = [C_BLUE,C_GREEN,C_RED,C_PURPLE,C_BLUE,C_YELLOW,C_RED,C_GREEN,pct_col(tpct)]
    sum_t = Table([sl, sv], colWidths=[3.0*cm]*9)
    sum_ts = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),C_CARD),('BACKGROUND',(0,1),(-1,1),C_BG),
        ('TEXTCOLOR',(0,0),(-1,0),C_MUTED),('FONTNAME',(0,0),(-1,0),'Helvetica'),('FONTSIZE',(0,0),(-1,0),7),
        ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,1),(-1,1),13),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('GRID',(0,0),(-1,-1),.5,C_BORDER)])
    for i, col in enumerate(sc): sum_ts.add('TEXTCOLOR',(i,1),(i,1),col)
    sum_t.setStyle(sum_ts); story.append(sum_t)

    # ── Tabela de frequência por turma ──────────────────────────────────
    story.append(Paragraph('Detalhamento por Turma', sSc))
    if show_cong:
        headers = ['Congregação','Turma','Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Freq.']
        cw = [3.5*cm,3*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,1.8*cm,1.8*cm,2.7*cm,1.8*cm]
        rows = [headers]+[[s['congregation'],s['name'],str(s['enrolled']),str(s['present']),str(s['absent']),str(s['visitors']),str(s['total_geral']),str(s['bibles']),str(s['magazines']),_fmt_cur(s['offering']),f"{s['pct']}%"] for s in class_stats]
        rows.append(['TOTAL','—',str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%'])
    else:
        headers = ['Turma','Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Freq.']
        cw = [3.8*cm,2.4*cm,2.4*cm,2.4*cm,2.4*cm,2.4*cm,2*cm,2*cm,3*cm,2*cm]
        rows = [headers]+[[s['name'],str(s['enrolled']),str(s['present']),str(s['absent']),str(s['visitors']),str(s['total_geral']),str(s['bibles']),str(s['magazines']),_fmt_cur(s['offering']),f"{s['pct']}%"] for s in class_stats]
        rows.append(['TOTAL',str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%'])

    freq_col = len(headers)-1
    det_t = Table(rows, colWidths=cw, repeatRows=1)
    det_ts = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),C_HEAD),('TEXTCOLOR',(0,0),(-1,0),C_WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[C_BG,C_CARD]),('TEXTCOLOR',(0,1),(-1,-2),C_WHITE),
        ('BACKGROUND',(0,-1),(-1,-1),C_CARD2),('TEXTCOLOR',(0,-1),(-1,-1),C_WHITE),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('LINEABOVE',(0,-1),(-1,-1),1.5,C_HEAD),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('ALIGN',(0,1),(0,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,1),(0,-1),6),
        ('GRID',(0,0),(-1,-1),.4,C_BORDER)])
    pc = 2 if show_cong else 1
    ac = 3 if show_cong else 2
    for i, s in enumerate(class_stats, start=1):
        det_ts.add('TEXTCOLOR',(pc,i),(pc,i),C_GREEN)
        det_ts.add('TEXTCOLOR',(ac,i),(ac,i),C_RED)
        det_ts.add('TEXTCOLOR',(freq_col,i),(freq_col,i),pct_col(s['pct']))
    tr = len(rows)-1
    det_ts.add('TEXTCOLOR',(pc,tr),(pc,tr),C_GREEN)
    det_ts.add('TEXTCOLOR',(ac,tr),(ac,tr),C_RED)
    det_ts.add('TEXTCOLOR',(freq_col,tr),(freq_col,tr),pct_col(tpct))
    det_t.setStyle(det_ts); story.append(det_t)

    # ── Seção de Visitantes (só quando lição selecionada) ───────────────
    if visitors_list:
        story.append(Paragraph(f'Visitantes da Licao: {lesson_title}', sSc))
        v_headers = ['Nome', 'Telefone', 'Igreja de Origem', 'Observações']
        v_cw = [page_w*0.28, page_w*0.15, page_w*0.25, page_w*0.32]
        v_rows = [v_headers]
        for v in visitors_list:
            v_rows.append([
                v.name,
                v.phone or '—',
                v.church or '—',
                v.notes or '—',
            ])
        v_t = Table(v_rows, colWidths=v_cw, repeatRows=1)
        v_ts = TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),  C_PURPLE),
            ('TEXTCOLOR',     (0,0),  (-1,0),  C_WHITE),
            ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),  (-1,-1), 7),
            ('ROWBACKGROUNDS',(0,1),  (-1,-1), [C_BG, C_CARD]),
            ('TEXTCOLOR',     (0,1),  (-1,-1), C_WHITE),
            ('ALIGN',         (0,0),  (-1,-1), 'LEFT'),
            ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),  (-1,-1), 6),
            ('BOTTOMPADDING', (0,0),  (-1,-1), 6),
            ('LEFTPADDING',   (0,0),  (-1,-1), 8),
            ('GRID',          (0,0),  (-1,-1), .4, C_BORDER),
        ])
        v_t.setStyle(v_ts); story.append(v_t)

        # Resumo de visitantes
        v_summary = Paragraph(
            f'Total de visitantes nesta licao: <b>{len(visitors_list)}</b>',
            ParagraphStyle('vs', fontSize=8, textColor=C_MUTED, fontName='Helvetica',
                           spaceBefore=4, leftIndent=4))
        story.append(v_summary)

    # ── Rodapé ──────────────────────────────────────────────────────────
    story.append(Spacer(1, .4*cm))
    story.append(HRFlowable(width='100%', thickness=.5, color=C_BORDER))
    story.append(Paragraph(f'EBD - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', sFt))
    doc.build(story); buf.seek(0)
    fname = f'relatorio_ebd_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp  = make_response(buf.read())
    resp.headers['Content-Type']        = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp


# ── Relatório de Membros (PDF) ────────────────────────────────────────────
@reports_bp.route('/membros-pdf')
@login_required
@admin_required
def membros_pdf():
    """PDF com listagem de membros: alunos por turma, professores e usuários."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer, HRFlowable, KeepTogether)
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        return "Erro: instale reportlab", 500

    import io
    from datetime import date
    from app.models.student import Student
    from app.models.teacher import Teacher
    from app.models.user import User
    from app.models.klass import Class
    from app.models.church import Church, Congregation

    C_BG=colors.HexColor('#0f1623'); C_CARD=colors.HexColor('#151d2e')
    C_CARD2=colors.HexColor('#1a2438'); C_HEAD=colors.HexColor('#2d9cdb')
    C_BORDER=colors.HexColor('#1e2d44'); C_MUTED=colors.HexColor('#94a3b8')
    C_WHITE=colors.white; C_GREEN=colors.HexColor('#10b981')
    C_YELLOW=colors.HexColor('#f59e0b'); C_PURPLE=colors.HexColor('#8b5cf6')

    def ps(name, **kw):
        defaults = dict(fontName='Helvetica', fontSize=9, textColor=C_WHITE, leading=13, spaceAfter=0)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    sTitle  = ps('T',  fontName='Helvetica-Bold', fontSize=20, textColor=C_HEAD,  spaceAfter=4, leading=24)
    sSubtitle=ps('St', fontSize=10, textColor=C_MUTED, spaceAfter=2)
    sChurch = ps('Ch', fontName='Helvetica-Bold', fontSize=13, textColor=C_WHITE,  spaceAfter=2)
    sCong   = ps('Cg', fontSize=9,  textColor=C_MUTED, spaceAfter=0)
    sSec    = ps('S',  fontName='Helvetica-Bold', fontSize=11, textColor=C_HEAD,   spaceBefore=14, spaceAfter=6)
    sSub    = ps('Sb', fontName='Helvetica-Bold', fontSize=9,  textColor=C_YELLOW, spaceBefore=8,  spaceAfter=4)
    sFooter = ps('F',  fontSize=7, textColor=C_MUTED, alignment=TA_CENTER, spaceBefore=6)
    sCellMuted = ps('Cm', fontSize=8, textColor=C_MUTED)

    def calc_age(birth):
        if not birth: return '—'
        today = date.today()
        return str(today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day)))

    def fmt_date(d):  return d.strftime('%d/%m/%Y') if d else '—'
    def fmt_bday(d):  return d.strftime('%d/%m')    if d else '—'

    cong_ids = congregation_ids()
    congregations = []
    church = None
    if cong_ids:
        congregations = Congregation.query.filter(Congregation.id.in_(cong_ids)).order_by(Congregation.name).all()
        if congregations:
            church = Church.query.get(congregations[0].church_id)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.8*cm,  bottomMargin=1.8*cm)
    story = []
    page_w = A4[0] - 3.6*cm

    story.append(Paragraph('EBD – Relatorio de Membros', sTitle))
    story.append(Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}', sSubtitle))
    story.append(Spacer(1, .3*cm))
    if church:
        story.append(Paragraph(f'Igreja: {church.name}', sChurch))
        story.append(Paragraph(f'Congregacao(oes): {", ".join(c.name for c in congregations)}', sCong))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER, spaceAfter=6))

    def make_table(headers, rows, col_widths, alt_col=None):
        all_rows = [headers] + rows
        t = Table(all_rows, colWidths=col_widths, repeatRows=1)
        ts = TableStyle([
            ('BACKGROUND',(0,0),(-1,0),C_HEAD),('TEXTCOLOR',(0,0),(-1,0),C_WHITE),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_BG,C_CARD]),('TEXTCOLOR',(0,1),(-1,-1),C_WHITE),
            ('ALIGN',(0,0),(-1,-1),'LEFT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),.3,C_BORDER),
        ])
        if alt_col is not None:
            for i in range(1, len(all_rows)):
                ts.add('TEXTCOLOR',(alt_col,i),(alt_col,i),C_MUTED)
        t.setStyle(ts); return t

    # Alunos por turma
    story.append(Paragraph('Alunos por Turma', sSec))
    classes = Class.query.filter(Class.congregation_id.in_(cong_ids)).order_by(Class.name).all()
    if not classes:
        story.append(Paragraph('Nenhuma turma cadastrada.', sCellMuted))
    else:
        for klass in classes:
            students_sorted = sorted(klass.students, key=lambda s: s.name)
            lbl = f'Turma: {klass.name}'
            if klass.congregation: lbl += f'  ·  {klass.congregation.name}'
            story.append(Paragraph(lbl, sSub))
            if not students_sorted:
                story.append(Paragraph('  Nenhum aluno matriculado.', sCellMuted)); continue
            headers = ['Nome','Idade','Aniversario','Email']
            cw = [page_w*0.38, page_w*0.10, page_w*0.14, page_w*0.38]
            rows = [[s.name, calc_age(s.birth_date), fmt_bday(s.birth_date), s.email or '—'] for s in students_sorted]
            story.append(KeepTogether([make_table(headers, rows, cw)]))
            story.append(Spacer(1, .2*cm))

    # Professores
    story.append(Paragraph('Professores', sSec))
    teachers = Teacher.query.filter(Teacher.congregation_id.in_(cong_ids)).order_by(Teacher.name).all()
    if not teachers:
        story.append(Paragraph('Nenhum professor cadastrado.', sCellMuted))
    else:
        headers = ['Nome','Aniversario','Email','Telefone']
        cw = [page_w*0.30, page_w*0.13, page_w*0.35, page_w*0.22]
        rows = [[t.name, fmt_date(t.birth_date), t.email or '—', t.phone or '—'] for t in teachers]
        story.append(make_table(headers, rows, cw, alt_col=3))

    # Usuários
    story.append(Paragraph('Usuarios do Sistema', sSec))
    from app.models.teacher import Teacher as T2
    users = User.query.filter(User.congregation_id.in_(cong_ids)).order_by(User.role, User.name).all()
    if current_user.is_superadmin and church:
        church_admins = User.query.filter(User.church_id==church.id, User.role.in_(('CHURCH_ADMIN','SUPERADMIN'))).order_by(User.name).all()
        ex = {u.id for u in users}
        users = list(users) + [u for u in church_admins if u.id not in ex]
        users.sort(key=lambda u: (u.role, u.name))
    ROLE_LABEL = {'SUPERADMIN':'Super Admin','CHURCH_ADMIN':'Admin Igreja','ADMIN':'Admin Cong.','TEACHER':'Professor'}
    if not users:
        story.append(Paragraph('Nenhum usuário cadastrado.', sCellMuted))
    else:
        headers = ['Nome','Perfil','Email','Telefone']
        cw = [page_w*0.28, page_w*0.14, page_w*0.36, page_w*0.22]
        rows = []
        for u in users:
            ph = '—'
            tr = T2.query.filter_by(user_id=u.id).first()
            if tr and tr.phone: ph = tr.phone
            rows.append([u.name, ROLE_LABEL.get(u.role, u.role), u.email, ph])
        story.append(make_table(headers, rows, cw, alt_col=1))

    story.append(Spacer(1, .5*cm))
    story.append(HRFlowable(width='100%', thickness=.5, color=C_BORDER))
    story.append(Paragraph(f'EBD – Relatorio de Membros  ·  {datetime.now().strftime("%d/%m/%Y %H:%M")}', sFooter))
    doc.build(story); buf.seek(0)
    fname = f'membros_ebd_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp  = make_response(buf.read())
    resp.headers['Content-Type']        = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp


# ── Relatório de Aniversariantes (PDF) ───────────────────────────────────────
@reports_bp.route('/aniversariantes-pdf')
@login_required
@admin_required
def aniversariantes_pdf():
    """PDF com aniversariantes filtrado por mês ou todos."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer, HRFlowable, KeepTogether)
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        return "Erro: instale reportlab", 500

    import io
    from datetime import date
    from app.models.student  import Student
    from app.models.teacher  import Teacher
    from app.models.klass    import Class
    from app.models.church   import Church, Congregation

    mes_param = request.args.get('mes', 'todos')   # 'todos' ou '1'..'12'
    cong_ids  = congregation_ids()

    MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    def calc_age(birth):
        if not birth: return '—'
        today = date.today()
        return str(today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day)))

    def fmt_date(d): return d.strftime('%d/%m/%Y') if d else '—'

    # ── Cores ──────────────────────────────────────────────────────────────
    C_BG     = colors.HexColor('#0f1623')
    C_CARD   = colors.HexColor('#151d2e')
    C_CARD2  = colors.HexColor('#1a2438')
    C_HEAD   = colors.HexColor('#2d9cdb')
    C_BORDER = colors.HexColor('#1e2d44')
    C_MUTED  = colors.HexColor('#94a3b8')
    C_WHITE  = colors.white
    C_GREEN  = colors.HexColor('#10b981')
    C_YELLOW = colors.HexColor('#f59e0b')
    C_PINK   = colors.HexColor('#ec4899')
    C_PURPLE = colors.HexColor('#8b5cf6')

    def ps(name, **kw):
        d = dict(fontName='Helvetica', fontSize=9, textColor=C_WHITE, leading=13)
        d.update(kw); return ParagraphStyle(name, **d)

    sTitle   = ps('T',  fontName='Helvetica-Bold', fontSize=20, textColor=C_HEAD,   spaceAfter=4,  leading=24)
    sSub     = ps('St', fontSize=9,  textColor=C_MUTED,  spaceAfter=2)
    sChurch  = ps('Ch', fontName='Helvetica-Bold', fontSize=13, textColor=C_WHITE,  spaceAfter=2)
    sCong    = ps('Cg', fontSize=9,  textColor=C_MUTED,  spaceAfter=6)
    sSec     = ps('S',  fontName='Helvetica-Bold', fontSize=11, textColor=C_HEAD,   spaceBefore=14, spaceAfter=6)
    sFooter  = ps('F',  fontSize=7,  textColor=C_MUTED,  alignment=TA_CENTER, spaceBefore=6)
    sCellM   = ps('Cm', fontSize=8,  textColor=C_MUTED)

    # ── Identificação da Igreja ─────────────────────────────────────────────
    congregations = []
    church = None
    if cong_ids:
        congregations = Congregation.query.filter(Congregation.id.in_(cong_ids)).order_by(Congregation.name).all()
        if congregations:
            church = Church.query.get(congregations[0].church_id)

    # ── Busca alunos e professores ──────────────────────────────────────────
    sq = Student.query.filter(Student.congregation_id.in_(cong_ids), Student.active == True)
    tq = Teacher.query.filter(Teacher.congregation_id.in_(cong_ids), Teacher.active == True)

    if mes_param != 'todos':
        try:
            mes_int = int(mes_param)
            from sqlalchemy import func as sqlfunc
            sq = sq.filter(sqlfunc.extract('month', Student.birth_date) == mes_int)
            tq = tq.filter(sqlfunc.extract('month', Teacher.birth_date) == mes_int)
        except ValueError:
            pass

    students = sq.order_by(Student.name).all()
    teachers = tq.order_by(Teacher.name).all()

    # Monta lista unificada com turmas dos alunos
    def turmas_aluno(s):
        nomes = [k.name for k in s.classes] if hasattr(s, 'classes') else []
        return ', '.join(nomes) if nomes else '—'

    rows_alunos = []
    for s in students:
        rows_alunos.append({
            'nome':       s.name,
            'aniversario': fmt_date(s.birth_date),
            'mes':         s.birth_date.month if s.birth_date else 99,
            'dia':         s.birth_date.day   if s.birth_date else 0,
            'idade':       calc_age(s.birth_date),
            'turma':       turmas_aluno(s),
            'telefone':    s.phone or '—',
            'email':       s.email or '—',
            'tipo':        'Aluno',
        })

    rows_professores = []
    for t in teachers:
        rows_professores.append({
            'nome':       t.name,
            'aniversario': fmt_date(t.birth_date),
            'mes':         t.birth_date.month if t.birth_date else 99,
            'dia':         t.birth_date.day   if t.birth_date else 0,
            'idade':       calc_age(t.birth_date),
            'turma':       '—',
            'telefone':    t.phone or '—',
            'email':       t.email or '—',
            'tipo':        'Professor',
        })

    # ── PDF ─────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.8*cm,  bottomMargin=1.8*cm)
    story = []
    page_w = A4[0] - 3.6*cm

    titulo_mes = MESES[mes_int-1] if mes_param != 'todos' else 'Todos os Meses'
    story.append(Paragraph(f'EBD – Aniversariantes', sTitle))
    story.append(Paragraph(f'{titulo_mes}  ·  Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}', sSub))
    story.append(Spacer(1, .3*cm))
    if church:
        story.append(Paragraph(f'Igreja: {church.name}', sChurch))
        story.append(Paragraph(f'Congregação(ões): {", ".join(c.name for c in congregations)}', sCong))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER, spaceAfter=6))

    def make_table(headers, rows, col_widths):
        all_rows = [headers] + rows
        t = Table(all_rows, colWidths=col_widths, repeatRows=1)
        ts = TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  C_HEAD),
            ('TEXTCOLOR',     (0,0), (-1,0),  C_WHITE),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_BG, C_CARD]),
            ('TEXTCOLOR',     (0,1), (-1,-1), C_WHITE),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('GRID',          (0,0), (-1,-1), .3, C_BORDER),
        ])
        # Cor da idade
        for i in range(1, len(all_rows)):
            ts.add('TEXTCOLOR', (3, i), (3, i), C_YELLOW)
        t.setStyle(ts); return t

    headers = ['Nome', 'Data de Aniversário', 'Tipo', 'Idade', 'Turma', 'Telefone', 'Email']
    cw = [page_w*0.22, page_w*0.13, page_w*0.09, page_w*0.07, page_w*0.16, page_w*0.14, page_w*0.19]

    def build_rows(lista):
        return [[r['nome'], r['aniversario'], r['tipo'], r['idade'],
                 r['turma'], r['telefone'], r['email']] for r in lista]

    if mes_param == 'todos':
        # Agrupa por mês
        from itertools import groupby
        tudo = sorted(rows_alunos + rows_professores, key=lambda x: (x['mes'], x['dia'], x['nome']))
        from itertools import groupby
        for mes_num, grupo in groupby(tudo, key=lambda x: x['mes']):
            items = list(grupo)
            label = MESES[mes_num-1] if mes_num <= 12 else '—'
            sec_style = ps(f'sec{mes_num}', fontName='Helvetica-Bold', fontSize=10,
                           textColor=C_PINK, spaceBefore=10, spaceAfter=4)
            story.append(Paragraph(f'🎂 {label}  ({len(items)} aniversariante{"s" if len(items)>1 else ""})', sec_style))
            story.append(KeepTogether([make_table(headers, build_rows(items), cw)]))
            story.append(Spacer(1, .2*cm))
    else:
        # Seção Alunos
        story.append(Paragraph(f'🎓 Alunos  ({len(rows_alunos)})', sSec))
        if rows_alunos:
            story.append(make_table(headers, build_rows(rows_alunos), cw))
        else:
            story.append(Paragraph('Nenhum aluno com aniversário neste mês.', sCellM))

        story.append(Spacer(1, .4*cm))

        # Seção Professores
        story.append(Paragraph(f'👨‍🏫 Professores  ({len(rows_professores)})', sSec))
        if rows_professores:
            story.append(make_table(headers, build_rows(rows_professores), cw))
        else:
            story.append(Paragraph('Nenhum professor com aniversário neste mês.', sCellM))

    # Rodapé
    story.append(Spacer(1, .5*cm))
    story.append(HRFlowable(width='100%', thickness=.5, color=C_BORDER))
    story.append(Paragraph(
        f'EBD – Aniversariantes {titulo_mes}  ·  {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        sFooter))

    doc.build(story); buf.seek(0)
    fname = f'aniversariantes_{mes_param}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp  = make_response(buf.read())
    resp.headers['Content-Type']        = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp
