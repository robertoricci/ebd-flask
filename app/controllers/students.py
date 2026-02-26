from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.student import Student
from app.utils.decorators import admin_required
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
    q = Student.query
    if search:
        q = q.filter(Student.name.ilike(f'%{search}%'))
    students = q.order_by(Student.name).all()
    return render_template('students/index.html', students=students, search=search)

@students_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    s = Student(
        name=request.form.get('name', '').strip(),
        email=request.form.get('email', '').strip() or None,
        phone=request.form.get('phone', '').strip() or None,
        birth_date=parse_date(request.form.get('birth_date')),
        notes=request.form.get('notes', '').strip() or None
    )
    db.session.add(s)
    db.session.commit()
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
    db.session.commit()
    flash('Aluno atualizado!', 'success')
    return redirect(url_for('students.index'))

@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    s = Student.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash('Aluno removido.', 'success')
    return redirect(url_for('students.index'))
