from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.teacher import Teacher
from app.models.user import User
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

def _available_users(congregation_id=None):
    """Usuários com role TEACHER que ainda não estão cadastrados como professor."""
    existing_user_ids = [t.user_id for t in Teacher.query.filter(Teacher.user_id.isnot(None)).all()]

    q = User.query.filter_by(role='TEACHER')
    if congregation_id:
        q = q.filter_by(congregation_id=congregation_id)
    elif current_user.congregation_id:
        q = q.filter_by(congregation_id=current_user.congregation_id)

    # Exclui quem já tem professor vinculado
    if existing_user_ids:
        q = q.filter(~User.id.in_(existing_user_ids))

    return q.order_by(User.name).all()

@teachers_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = scoped(Teacher)
    if search:
        q = q.filter(Teacher.name.ilike(f'%{search}%'))
    teachers = q.order_by(Teacher.name).all()
    congregations  = _visible_congregations()
    available_users = _available_users()
    return render_template('teachers/index.html', teachers=teachers, search=search,
                           congregations=congregations, available_users=available_users)

@teachers_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('Selecione um usuário do tipo Professor.', 'danger')
        return redirect(url_for('teachers.index'))

    user = User.query.get(user_id)
    if not user or user.role != 'TEACHER':
        flash('Usuário inválido ou não é do tipo Professor.', 'danger')
        return redirect(url_for('teachers.index'))

    # Verificar se já existe professor vinculado a este usuário
    if Teacher.query.filter_by(user_id=user_id).first():
        flash('Este usuário já está cadastrado como professor.', 'danger')
        return redirect(url_for('teachers.index'))

    congregation_id = user.congregation_id
    if current_user.is_superadmin or current_user.is_church_admin:
        congregation_id = request.form.get('congregation_id', type=int) or congregation_id

    t = Teacher(
        user_id=user_id,
        name=user.name,
        email=user.email,
        phone=request.form.get('phone', '').strip() or None,
        birth_date=parse_date(request.form.get('birth_date')),
        notes=request.form.get('notes', '').strip() or None,
        congregation_id=congregation_id,
    )
    db.session.add(t)
    db.session.commit()
    flash(f'Professor {user.name} cadastrado com sucesso!', 'success')
    return redirect(url_for('teachers.index'))

@teachers_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    t = Teacher.query.get_or_404(id)
    t.phone      = request.form.get('phone', '').strip() or None
    t.birth_date = parse_date(request.form.get('birth_date'))
    t.notes      = request.form.get('notes', '').strip() or None
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
    db.session.delete(t)
    db.session.commit()
    flash('Professor removido.', 'success')
    return redirect(url_for('teachers.index'))
