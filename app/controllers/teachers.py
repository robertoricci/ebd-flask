from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.teacher import Teacher
from app.models.church import Congregation
from app.utils.decorators import admin_required
from app.utils.scope import scoped
from datetime import datetime

teachers_bp = Blueprint('teachers', __name__, url_prefix='/professores')

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%d').date()
    except: return None

def _visible_congregations():
    if current_user.is_superadmin:
        return Congregation.query.order_by(Congregation.name).all()
    if current_user.is_church_admin:
        return Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    if current_user.congregation_id:
        return Congregation.query.filter_by(id=current_user.congregation_id).all()
    return []

@teachers_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = scoped(Teacher)
    if search:
        q = q.filter(Teacher.name.ilike(f'%{search}%'))
    teachers = q.order_by(Teacher.name).all()
    congregations = _visible_congregations()
    return render_template('teachers/index.html', teachers=teachers, search=search, congregations=congregations)

@teachers_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    congregation_id = request.form.get('congregation_id', type=int)
    if current_user.is_congregation_admin or (not current_user.is_superadmin and not current_user.is_church_admin):
        congregation_id = current_user.congregation_id
    t = Teacher(
        name=request.form.get('name', '').strip(),
        email=request.form.get('email', '').strip() or None,
        phone=request.form.get('phone', '').strip() or None,
        birth_date=parse_date(request.form.get('birth_date')),
        notes=request.form.get('notes', '').strip() or None,
        congregation_id=congregation_id,
    )
    db.session.add(t); db.session.commit()
    flash('Professor criado!', 'success')
    return redirect(url_for('teachers.index'))

@teachers_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    t = Teacher.query.get_or_404(id)
    t.name = request.form.get('name', t.name).strip()
    t.email = request.form.get('email', '').strip() or None
    t.phone = request.form.get('phone', '').strip() or None
    t.birth_date = parse_date(request.form.get('birth_date'))
    t.notes = request.form.get('notes', '').strip() or None
    if current_user.is_superadmin or current_user.is_church_admin:
        t.congregation_id = request.form.get('congregation_id', type=int) or t.congregation_id
    db.session.commit()
    flash('Professor atualizado!', 'success')
    return redirect(url_for('teachers.index'))

@teachers_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    t = Teacher.query.get_or_404(id)
    db.session.delete(t); db.session.commit()
    flash('Professor removido.', 'success')
    return redirect(url_for('teachers.index'))
