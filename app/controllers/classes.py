from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.klass import Class
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.church import Congregation
from app.utils.decorators import admin_required
from app.utils.scope import scoped

classes_bp = Blueprint('classes', __name__, url_prefix='/turmas')

def _visible_congregations():
    if current_user.is_superadmin:
        return Congregation.query.order_by(Congregation.name).all()
    if current_user.is_church_admin:
        return Congregation.query.filter_by(church_id=current_user.church_id).order_by(Congregation.name).all()
    if current_user.congregation_id:
        return Congregation.query.filter_by(id=current_user.congregation_id).all()
    return []

@classes_bp.route('/')
@login_required
@admin_required
def index():
    classes = scoped(Class).order_by(Class.name).all()
    congregations = _visible_congregations()
    return render_template('classes/index.html', classes=classes, congregations=congregations)

@classes_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    congregation_id = request.form.get('congregation_id', type=int)
    if not current_user.is_superadmin and not current_user.is_church_admin:
        congregation_id = current_user.congregation_id
    c = Class(
        name=request.form.get('name', '').strip(),
        description=request.form.get('description', '').strip() or None,
        congregation_id=congregation_id,
    )
    db.session.add(c); db.session.commit()
    flash('Turma criada!', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    c = Class.query.get_or_404(id)
    c.name = request.form.get('name', c.name).strip()
    c.description = request.form.get('description', '').strip() or None
    if current_user.is_superadmin or current_user.is_church_admin:
        c.congregation_id = request.form.get('congregation_id', type=int) or c.congregation_id
    db.session.commit()
    flash('Turma atualizada!', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    c = Class.query.get_or_404(id)
    db.session.delete(c); db.session.commit()
    flash('Turma removida.', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/members')
@login_required
@admin_required
def members(id):
    c = Class.query.get_or_404(id)
    ids = current_user.congregation_filter()
    all_students = Student.query.filter(Student.congregation_id.in_(ids)).order_by(Student.name).all()
    all_teachers = Teacher.query.filter(Teacher.congregation_id.in_(ids)).order_by(Teacher.name).all()
    member_students = [s.id for s in c.students]
    member_teachers = [t.id for t in c.teachers]
    return render_template('classes/members.html', klass=c,
        all_students=all_students, all_teachers=all_teachers,
        member_students=member_students, member_teachers=member_teachers)

@classes_bp.route('/<int:id>/members/update', methods=['POST'])
@login_required
@admin_required
def update_members(id):
    c = Class.query.get_or_404(id)
    student_ids = request.form.getlist('students', type=int)
    teacher_ids = request.form.getlist('teachers', type=int)
    c.students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    c.teachers = Teacher.query.filter(Teacher.id.in_(teacher_ids)).all() if teacher_ids else []
    db.session.commit()
    flash('Membros atualizados!', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/add-student', methods=['POST'])
@login_required
@admin_required
def add_student(id):
    c = Class.query.get_or_404(id)
    student_id = request.form.get('student_id', type=int)
    s = Student.query.get(student_id)
    if s and s not in c.students:
        c.students.append(s)
        db.session.commit()
    return jsonify({'ok': True})

@classes_bp.route('/<int:id>/remove-student', methods=['POST'])
@login_required
@admin_required
def remove_student(id):
    c = Class.query.get_or_404(id)
    student_id = request.form.get('student_id', type=int)
    s = Student.query.get(student_id)
    if s and s in c.students:
        c.students.remove(s)
        db.session.commit()
    return jsonify({'ok': True})
