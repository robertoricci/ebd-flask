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
    year         = request.args.get('year', type=int)
    trimester_id = request.args.get('trimester_id', type=int)
    class_id     = request.args.get('class_id', type=int)
    congregation_id = request.args.get('congregation_id', type=int)
    lesson_title = request.args.get('lesson_title', '').strip()
    return year, trimester_id, class_id, congregation_id, lesson_title


def _get_years():
    rows = db.session.query(Trimester.year).distinct().order_by(Trimester.year.desc()).all()
    return [r[0] for r in rows]


def _get_unique_lesson_titles(year=None, trimester_id=None, class_id=None, cong_ids=None):
    q = db.session.query(Lesson.title).distinct()
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


def _build_stats(year, trimester_id, class_id, congregation_id, lesson_title, cong_ids):
    # Filtrar classes pelo scope + congregação selecionada
    cq = Class.query.filter(Class.congregation_id.in_(cong_ids))
    if congregation_id and congregation_id in cong_ids:
        cq = cq.filter(Class.congregation_id == congregation_id)
    if class_id:
        cq = cq.filter(Class.id == class_id)
    classes = cq.order_by(Class.name).all()

    # Filtrar lições
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


@reports_bp.route('/')
@login_required
@admin_required
def index():
    cong_ids   = congregation_ids()
    years      = _get_years()
    year, trimester_id, class_id, congregation_id, lesson_title = _get_filters()

    tq = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter)
    if year: tq = tq.filter_by(year=year)
    trimesters = tq.all()

    # Congregações visíveis (para filtro extra no superadmin/church_admin)
    if current_user.is_superadmin:
        congregations = Congregation.query.order_by(Congregation.name).all()
    elif current_user.is_church_admin:
        congregations = Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    else:
        congregations = []

    # Filtrar cong_ids pelo filtro selecionado
    eff_cong_ids = cong_ids
    if congregation_id and congregation_id in cong_ids:
        eff_cong_ids = [congregation_id]

    cq = Class.query.filter(Class.congregation_id.in_(eff_cong_ids))
    if class_id: cq = cq.filter(Class.id == class_id)
    classes = cq.order_by(Class.name).all()
    lesson_titles = _get_unique_lesson_titles(year, trimester_id, class_id, eff_cong_ids)

    stats = _build_stats(year, trimester_id, class_id, congregation_id, lesson_title, cong_ids)
    class_stats, te, tp, ta, tv, tg, tpct, to_, tb, tm = stats

    filter_labels = []
    if year: filter_labels.append(('Ano', str(year)))
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: filter_labels.append(('Trimestre', t.name))
    if congregation_id:
        cg = Congregation.query.get(congregation_id)
        if cg: filter_labels.append(('Congregação', cg.name))
    if class_id:
        c = Class.query.get(class_id)
        if c: filter_labels.append(('Turma', c.name))
    if lesson_title:
        filter_labels.append(('Lição', lesson_title))

    show_congregation_col = current_user.is_superadmin or current_user.is_church_admin

    return render_template('reports/index.html',
        years=years, trimesters=trimesters, classes=classes,
        congregations=congregations, lesson_titles=lesson_titles,
        year=year, trimester_id=trimester_id, class_id=class_id,
        congregation_id=congregation_id, lesson_title=lesson_title,
        filter_labels=filter_labels, class_stats=class_stats,
        show_congregation_col=show_congregation_col,
        total_enrolled=te, total_present=tp, total_absent=ta,
        total_visitors=tv, total_geral=tg, total_pct=tpct,
        total_offering=to_, total_bibles=tb, total_magazines=tm)


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
    year, trimester_id, class_id, congregation_id, lesson_title = _get_filters()
    stats = _build_stats(year, trimester_id, class_id, congregation_id, lesson_title, cong_ids)
    class_stats, te, tp, ta, tv, tg, tpct, to_, tb, tm = stats
    show_cong = current_user.is_superadmin or current_user.is_church_admin

    filter_parts = []
    if year: filter_parts.append(f'Ano: {year}')
    if trimester_id:
        t = Trimester.query.get(trimester_id)
        if t: filter_parts.append(f'Trimestre: {t.name}')
    if congregation_id:
        cg = Congregation.query.get(congregation_id)
        if cg: filter_parts.append(f'Congregação: {cg.name}')
    if class_id:
        c = Class.query.get(class_id)
        if c: filter_parts.append(f'Turma: {c.name}')
    if lesson_title: filter_parts.append(f'Lição: {lesson_title}')

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

    sT=ParagraphStyle('sT',fontSize=18,textColor=C_HEAD,fontName='Helvetica-Bold',spaceAfter=3)
    sS=ParagraphStyle('sS',fontSize=8,textColor=C_MUTED,fontName='Helvetica',spaceAfter=6)
    sF=ParagraphStyle('sF',fontSize=8,textColor=C_WHITE,fontName='Helvetica-Bold',spaceAfter=12,backColor=C_CARD2,borderPad=5,leftIndent=4)
    sSc=ParagraphStyle('sSc',fontSize=9,textColor=C_MUTED,fontName='Helvetica-Bold',spaceAfter=6,spaceBefore=10)
    sFt=ParagraphStyle('sFt',fontSize=7,textColor=C_MUTED,fontName='Helvetica',alignment=TA_CENTER,spaceBefore=4)

    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=1.5*cm,rightMargin=1.5*cm,topMargin=1.5*cm,bottomMargin=1.5*cm)
    story=[]

    story.append(Paragraph('EBD - Relatorio de Frequencia',sT))
    story.append(Paragraph(f'Gerado em: {datetime.now().strftime("%d/%m/%Y as %H:%M")}',sS))
    story.append(Paragraph(f'Filtros: {"  |  ".join(filter_parts) if filter_parts else "Todos os dados"}',sF))

    # Cards resumo
    story.append(Paragraph('Resumo Geral',sSc))
    sl=['Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Frequencia']
    sv=[str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%']
    sc=[C_BLUE,C_GREEN,C_RED,C_PURPLE,C_BLUE,C_YELLOW,C_RED,C_GREEN,pct_col(tpct)]
    sum_t=Table([sl,sv],colWidths=[3.0*cm]*9)
    sum_ts=TableStyle([('BACKGROUND',(0,0),(-1,0),C_CARD),('BACKGROUND',(0,1),(-1,1),C_BG),
        ('TEXTCOLOR',(0,0),(-1,0),C_MUTED),('FONTNAME',(0,0),(-1,0),'Helvetica'),('FONTSIZE',(0,0),(-1,0),7),
        ('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,1),(-1,1),13),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),.5,C_BORDER)])
    for i,col in enumerate(sc): sum_ts.add('TEXTCOLOR',(i,1),(i,1),col)
    sum_t.setStyle(sum_ts); story.append(sum_t)

    # Tabela detalhada
    story.append(Paragraph('Detalhamento por Turma',sSc))
    if show_cong:
        headers=['Congregação','Turma','Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Freq.']
        cw=[3.5*cm,3*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,2.2*cm,1.8*cm,1.8*cm,2.7*cm,1.8*cm]
        rows=[headers]+[[s['congregation'],s['name'],str(s['enrolled']),str(s['present']),str(s['absent']),str(s['visitors']),str(s['total_geral']),str(s['bibles']),str(s['magazines']),_fmt_cur(s['offering']),f"{s['pct']}%"] for s in class_stats]
        rows.append(['TOTAL','—',str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%'])
    else:
        headers=['Turma','Matriculados','Presentes','Ausentes','Visitantes','Total P+V','Biblias','Revistas','Oferta','Freq.']
        cw=[3.8*cm,2.4*cm,2.4*cm,2.4*cm,2.4*cm,2.4*cm,2*cm,2*cm,3*cm,2*cm]
        rows=[headers]+[[s['name'],str(s['enrolled']),str(s['present']),str(s['absent']),str(s['visitors']),str(s['total_geral']),str(s['bibles']),str(s['magazines']),_fmt_cur(s['offering']),f"{s['pct']}%"] for s in class_stats]
        rows.append(['TOTAL',str(te),str(tp),str(ta),str(tv),str(tg),str(tb),str(tm),_fmt_cur(to_),f'{tpct}%'])

    freq_col=len(headers)-1
    det_t=Table(rows,colWidths=cw,repeatRows=1)
    det_ts=TableStyle([('BACKGROUND',(0,0),(-1,0),C_HEAD),('TEXTCOLOR',(0,0),(-1,0),C_WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[C_BG,C_CARD]),('TEXTCOLOR',(0,1),(-1,-2),C_WHITE),
        ('BACKGROUND',(0,-1),(-1,-1),C_CARD2),('TEXTCOLOR',(0,-1),(-1,-1),C_WHITE),
        ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('LINEABOVE',(0,-1),(-1,-1),1.5,C_HEAD),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('ALIGN',(0,1),(0,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,1),(0,-1),6),('GRID',(0,0),(-1,-1),.4,C_BORDER)])
    pc=2 if show_cong else 1; ac=3 if show_cong else 2
    for i,s in enumerate(class_stats,start=1):
        det_ts.add('TEXTCOLOR',(pc,i),(pc,i),C_GREEN)
        det_ts.add('TEXTCOLOR',(ac,i),(ac,i),C_RED)
        det_ts.add('TEXTCOLOR',(freq_col,i),(freq_col,i),pct_col(s['pct']))
    tr=len(rows)-1
    det_ts.add('TEXTCOLOR',(pc,tr),(pc,tr),C_GREEN)
    det_ts.add('TEXTCOLOR',(ac,tr),(ac,tr),C_RED)
    det_ts.add('TEXTCOLOR',(freq_col,tr),(freq_col,tr),pct_col(tpct))
    det_t.setStyle(det_ts); story.append(det_t)

    story.append(Spacer(1,.4*cm))
    story.append(HRFlowable(width='100%',thickness=.5,color=C_BORDER))
    story.append(Paragraph(f'EBD - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}',sFt))
    doc.build(story); buf.seek(0)
    fname=f'relatorio_ebd_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp=make_response(buf.read())
    resp.headers['Content-Type']='application/pdf'
    resp.headers['Content-Disposition']=f'attachment; filename={fname}'
    return resp
