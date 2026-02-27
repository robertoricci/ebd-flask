from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.church import Church, Congregation
from app.utils.decorators import admin_required

users_bp = Blueprint('users', __name__, url_prefix='/usuarios')

def _visible_congregations():
    """Congregações que o usuário logado pode gerenciar."""
    if current_user.is_superadmin:
        return Congregation.query.order_by(Congregation.name).all()
    if current_user.is_church_admin:
        return Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    if current_user.congregation_id:
        return Congregation.query.filter_by(id=current_user.congregation_id).all()
    return []

@users_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = User.query
    # Filtra por congregações visíveis
    if not current_user.is_superadmin:
        ids = current_user.congregation_filter()
        q = q.filter(User.congregation_id.in_(ids))
    if search:
        q = q.filter(User.name.ilike(f'%{search}%'))
    users = q.order_by(User.name).all()
    congregations = _visible_congregations()
    churches = Church.query.order_by(Church.name).all() if current_user.is_superadmin else []
    return render_template('users/index.html', users=users, search=search,
                           congregations=congregations, churches=churches)

@users_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    name  = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role  = request.form.get('role', 'TEACHER')
    congregation_id = request.form.get('congregation_id', type=int) or None
    church_id = request.form.get('church_id', type=int) or None

    # Proteção: não-superadmin não pode criar SUPERADMIN ou CHURCH_ADMIN
    if not current_user.is_superadmin and role in ('SUPERADMIN', 'CHURCH_ADMIN'):
        flash('Sem permissão para criar este tipo de usuário.', 'danger')
        return redirect(url_for('users.index'))
    # Admin de congregação só cria na sua congregação
    if current_user.is_congregation_admin:
        congregation_id = current_user.congregation_id
        church_id = None

    if not name or not email or not password:
        flash('Nome, email e senha são obrigatórios.', 'danger')
        return redirect(url_for('users.index'))
    if User.query.filter_by(email=email).first():
        flash('Email já cadastrado.', 'danger')
        return redirect(url_for('users.index'))

    u = User(name=name, email=email, role=role,
             congregation_id=congregation_id, church_id=church_id)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash('Usuário criado com sucesso!', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    u = User.query.get_or_404(id)
    u.name  = request.form.get('name', u.name).strip()
    u.email = request.form.get('email', u.email).strip()
    role = request.form.get('role', u.role)
    if current_user.is_superadmin:
        u.role = role
        u.congregation_id = request.form.get('congregation_id', type=int) or None
        u.church_id = request.form.get('church_id', type=int) or None
    elif current_user.is_church_admin:
        if role not in ('SUPERADMIN', 'CHURCH_ADMIN'):
            u.role = role
        u.congregation_id = request.form.get('congregation_id', type=int) or None
    pw = request.form.get('password', '')
    if pw:
        u.set_password(pw)
    db.session.commit()
    flash('Usuário atualizado!', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    u = User.query.get_or_404(id)
    db.session.delete(u)
    db.session.commit()
    flash('Usuário removido.', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle(id):
    u = User.query.get_or_404(id)
    u.active = not u.active
    db.session.commit()
    return jsonify({'active': u.active})

@users_bp.route('/congregations-by-church')
@login_required
@admin_required
def congregations_by_church():
    """AJAX: retorna congregações de uma igreja."""
    church_id = request.args.get('church_id', type=int)
    congs = Congregation.query.filter_by(church_id=church_id).order_by(Congregation.name).all() if church_id else []
    return jsonify([{'id': c.id, 'name': c.name} for c in congs])
