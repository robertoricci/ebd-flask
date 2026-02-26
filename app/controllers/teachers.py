from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.teacher import Teacher
from app.utils.decorators import admin_required
from datetime import datetime

teachers_bp = Blueprint('teachers', __name__, url_prefix='/professores')

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except:
        return None

@teachers_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = Teacher.query
    if search:
        q = q.filter(Teacher.name.ilike(f'%{search}%'))
    teachers = q.order_by(Teacher.name).all()
    return render_template('teachers/index.html', teachers=teachers, search=search)

@teachers_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    t = Teacher(
        name=request.form.get('name', '').strip(),
        email=request.form.get('email', '').strip() or None,
        phone=request.form.get('phone', '').strip() or None,
        birth_date=parse_date(request.form.get('birth_date')),
        notes=request.form.get('notes', '').strip() or None
    )
    db.session.add(t)
    db.session.commit()
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
