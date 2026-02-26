from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models.user import User
from app.utils.decorators import admin_required

users_bp = Blueprint('users', __name__, url_prefix='/usuarios')

@users_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = User.query
    if search:
        q = q.filter(User.name.ilike(f'%{search}%'))
    users = q.order_by(User.name).all()
    return render_template('users/index.html', users=users, search=search)

@users_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'TEACHER')
    if not name or not email or not password:
        flash('Nome, email e senha são obrigatórios.', 'danger')
        return redirect(url_for('users.index'))
    if User.query.filter_by(email=email).first():
        flash('Email já cadastrado.', 'danger')
        return redirect(url_for('users.index'))
    u = User(name=name, email=email, role=role)
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
    u.name = request.form.get('name', u.name).strip()
    u.email = request.form.get('email', u.email).strip()
    u.role = request.form.get('role', u.role)
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
