from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app import db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.klass   import Class
from app.models.church  import Congregation, Church
from app.utils.scope    import congregation_ids
from sqlalchemy import func
from datetime import date, datetime

birthdays_bp = Blueprint('birthdays', __name__, url_prefix='/aniversarios')

MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
         'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']


def _calc_age(birth):
    if not birth:
        return None
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _get_scope():
    """
    Retorna os class_ids permitidos para o usuário atual.
    - SUPERADMIN / CHURCH_ADMIN / ADMIN → todos da(s) congregação(ões)
    - TEACHER / SECRETARY              → somente a turma vinculada
    """
    cong_ids = congregation_ids()

    if current_user.is_secretary or current_user.role == 'TEACHER':
        # Limita à turma vinculada ao usuário
        if current_user.class_id:
            return cong_ids, [current_user.class_id]
        return cong_ids, []

    # Admin e acima: todas as turmas das congregações visíveis
    classes = Class.query.filter(Class.congregation_id.in_(cong_ids)).all()
    return cong_ids, [c.id for c in classes]


def _build_list(mes_param, cong_ids, class_ids):
    """Monta lista unificada de aniversariantes."""
    today = date.today()

    # Alunos
    sq = Student.query.filter(
        Student.congregation_id.in_(cong_ids),
        Student.active == True,
        Student.birth_date.isnot(None)
    )
    if class_ids is not None:
        # Filtra somente alunos que estão nas turmas permitidas
        from app.models.student import class_students
        from sqlalchemy import select
        allowed_student_ids = db.session.execute(
            select(class_students.c.student_id).where(
                class_students.c.class_id.in_(class_ids)
            )
        ).scalars().all()
        sq = sq.filter(Student.id.in_(allowed_student_ids))

    # Professores (não filtra por turma para TEACHER/SECRETARY — só alunos)
    tq = Teacher.query.filter(
        Teacher.congregation_id.in_(cong_ids),
        Teacher.active == True,
        Teacher.birth_date.isnot(None)
    )

    if mes_param and mes_param != 'todos':
        try:
            m = int(mes_param)
            sq = sq.filter(func.extract('month', Student.birth_date) == m)
            tq = tq.filter(func.extract('month', Teacher.birth_date) == m)
        except ValueError:
            pass

    def turmas(s):
        nomes = [k.name for k in s.classes] if hasattr(s, 'classes') else []
        return ', '.join(nomes) if nomes else '—'

    items = []
    for s in sq.order_by(Student.name).all():
        items.append({
            'name':       s.name,
            'birth_date': s.birth_date,
            'age':        _calc_age(s.birth_date),
            'type':       'Aluno',
            'turma':      turmas(s),
            'telefone':   s.phone or '—',
            'email':      s.email or '—',
        })

    # Professores — só inclui se não for SECRETARY/TEACHER com turma restrita
    if not (current_user.is_secretary or current_user.role == 'TEACHER'):
        for t in tq.order_by(Teacher.name).all():
            items.append({
                'name':       t.name,
                'birth_date': t.birth_date,
                'age':        _calc_age(t.birth_date),
                'type':       'Professor',
                'turma':      '—',
                'telefone':   t.phone or '—',
                'email':      t.email or '—',
            })

    # Ordena
    if mes_param and mes_param != 'todos':
        items.sort(key=lambda x: (x['birth_date'].day if x['birth_date'] else 0))
    else:
        items.sort(key=lambda x: (
            x['birth_date'].month if x['birth_date'] else 13,
            x['birth_date'].day   if x['birth_date'] else 0,
        ))

    return items


# ── Index ─────────────────────────────────────────────────────────────────────
@birthdays_bp.route('/')
@login_required
def index():
    mes_param = request.args.get('mes', str(date.today().month))  # default = mês atual
    cong_ids, class_ids = _get_scope()
    birthday_list = _build_list(mes_param, cong_ids, class_ids)

    # Congregações para exibição de contexto
    congregations = Congregation.query.filter(
        Congregation.id.in_(cong_ids)
    ).order_by(Congregation.name).all()

    return render_template('birthdays/index.html',
        birthday_list=birthday_list,
        mes_param=mes_param,
        MESES=MESES,
        today=date.today(),
        congregations=congregations,
    )


# ── PDF ───────────────────────────────────────────────────────────────────────
@birthdays_bp.route('/pdf')
@login_required
def pdf():
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

    mes_param  = request.args.get('mes', 'todos')
    cong_ids, class_ids = _get_scope()
    items      = _build_list(mes_param, cong_ids, class_ids)

    # Identificação
    congregations = Congregation.query.filter(Congregation.id.in_(cong_ids)).all()
    church = None
    if congregations:
        church = Church.query.get(congregations[0].church_id)

    titulo_mes = MESES[int(mes_param)-1] if mes_param not in ('', 'todos') else 'Todos os Meses'

    # ── Cores ──────────────────────────────────────────────────────────────
    C_BG     = colors.HexColor('#0f1623')
    C_CARD   = colors.HexColor('#151d2e')
    C_CARD2  = colors.HexColor('#1a2438')
    C_HEAD   = colors.HexColor('#2d9cdb')
    C_BORDER = colors.HexColor('#1e2d44')
    C_MUTED  = colors.HexColor('#94a3b8')
    C_WHITE  = colors.white
    C_YELLOW = colors.HexColor('#f59e0b')
    C_PINK   = colors.HexColor('#ec4899')

    def ps(name, **kw):
        d = dict(fontName='Helvetica', fontSize=9, textColor=C_WHITE, leading=13)
        d.update(kw)
        return ParagraphStyle(name, **d)

    sTitle  = ps('T',  fontName='Helvetica-Bold', fontSize=20, textColor=C_HEAD, spaceAfter=4, leading=24)
    sSub    = ps('St', fontSize=9, textColor=C_MUTED, spaceAfter=2)
    sChurch = ps('Ch', fontName='Helvetica-Bold', fontSize=13, textColor=C_WHITE, spaceAfter=2)
    sCong   = ps('Cg', fontSize=9, textColor=C_MUTED, spaceAfter=6)
    sSec    = ps('S',  fontName='Helvetica-Bold', fontSize=11, textColor=C_PINK, spaceBefore=12, spaceAfter=4)
    sFooter = ps('F',  fontSize=7, textColor=C_MUTED, alignment=TA_CENTER, spaceBefore=6)
    sCellM  = ps('Cm', fontSize=8, textColor=C_MUTED)

    headers = ['Nome', 'Aniversário', 'Tipo', 'Idade', 'Turma', 'Telefone', 'Email']

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.8*cm,  bottomMargin=1.8*cm)
    story = []
    page_w = A4[0] - 3.6*cm
    cw = [page_w*0.20, page_w*0.12, page_w*0.09, page_w*0.07,
          page_w*0.18, page_w*0.14, page_w*0.20]

    story.append(Paragraph('EBD – Aniversariantes', sTitle))
    story.append(Paragraph(
        f'{titulo_mes}  ·  Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}', sSub))
    story.append(Spacer(1, .3*cm))
    if church:
        story.append(Paragraph(f'Igreja: {church.name}', sChurch))
        story.append(Paragraph(
            f'Congregação(ões): {", ".join(c.name for c in congregations)}', sCong))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER, spaceAfter=6))

    def make_table(rows_data):
        all_rows = [headers] + rows_data
        t = Table(all_rows, colWidths=cw, repeatRows=1)
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
        for i in range(1, len(all_rows)):
            ts.add('TEXTCOLOR', (3, i), (3, i), C_YELLOW)  # idade em amarelo
        t.setStyle(ts)
        return t

    def fmt(r):
        return [r['name'],
                r['birth_date'].strftime('%d/%m/%Y') if r['birth_date'] else '—',
                r['type'], str(r['age']) if r['age'] else '—',
                r['turma'], r['telefone'], r['email']]

    if mes_param in ('', 'todos'):
        # Agrupa por mês
        from itertools import groupby
        grouped = {}
        for item in items:
            m = item['birth_date'].month if item['birth_date'] else 0
            grouped.setdefault(m, []).append(item)
        for m in sorted(grouped.keys()):
            label = MESES[m-1] if m >= 1 else '—'
            group = grouped[m]
            story.append(Paragraph(
                f'🎂 {label}  ({len(group)} aniversariante{"s" if len(group)>1 else ""})', sSec))
            story.append(KeepTogether([make_table([fmt(r) for r in group])]))
            story.append(Spacer(1, .3*cm))
    else:
        if items:
            story.append(make_table([fmt(r) for r in items]))
        else:
            story.append(Paragraph('Nenhum aniversariante neste mês.', sCellM))

    story.append(Spacer(1, .5*cm))
    story.append(HRFlowable(width='100%', thickness=.5, color=C_BORDER))
    story.append(Paragraph(
        f'EBD – Aniversariantes {titulo_mes}  ·  {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        sFooter))

    doc.build(story)
    buf.seek(0)
    fname = f'aniversariantes_{mes_param}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    resp  = make_response(buf.read())
    resp.headers['Content-Type']        = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={fname}'
    return resp
