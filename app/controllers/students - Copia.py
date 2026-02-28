from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.student import Student
from app.models.church import Congregation
from app.utils.decorators import admin_required
from app.utils.scope import scoped
from datetime import datetime

students_bp = Blueprint('students', __name__, url_prefix='/alunos')

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%d').date()
    except: return None

@students_bp.route('/')
@login_required
@admin_required
def index():
    search = request.args.get('q', '')
    q = scoped(Student)
    if search:
        q = q.filter(Student.name.ilike(f'%{search}%'))
    students = q.order_by(Student.name).all()
    congregations = _visible_congregations()
    return render_template('students/index.html', students=students, search=search, congregations=congregations)

def _visible_congregations():
    if current_user.is_superadmin:
        return Congregation.query.order_by(Congregation.name).all()
    if current_user.is_church_admin:
        return Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    if current_user.congregation_id:
        return Congregation.query.filter_by(id=current_user.congregation_id).all()
    return []

@students_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    congregation_id = request.form.get('congregation_id', type=int)
    if current_user.is_congregation_admin or (not current_user.is_superadmin and not current_user.is_church_admin):
        congregation_id = current_user.congregation_id
    s = Student(
        name=request.form.get('name', '').strip(),
        email=request.form.get('email', '').strip() or None,
        phone=request.form.get('phone', '').strip() or None,
        birth_date=parse_date(request.form.get('birth_date')),
        notes=request.form.get('notes', '').strip() or None,
        congregation_id=congregation_id,
    )
    db.session.add(s); db.session.commit()
    flash('Aluno criado!', 'success')
    return redirect(url_for('students.index'))

@students_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    s = Student.query.get_or_404(id)
    s.name = request.form.get('name', s.name).strip()
    s.email = request.form.get('email', '').strip() or None
    s.phone = request.form.get('phone', '').strip() or None
    s.birth_date = parse_date(request.form.get('birth_date'))
    s.notes = request.form.get('notes', '').strip() or None
    if current_user.is_superadmin or current_user.is_church_admin:
        s.congregation_id = request.form.get('congregation_id', type=int) or s.congregation_id
    db.session.commit()
    flash('Aluno atualizado!', 'success')
    return redirect(url_for('students.index'))

@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    s = Student.query.get_or_404(id)
    db.session.delete(s); db.session.commit()
    flash('Aluno removido.', 'success')
    return redirect(url_for('students.index'))
