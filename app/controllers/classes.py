from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models.klass import Class
from app.models.student import Student
from app.models.teacher import Teacher
from app.utils.decorators import admin_required

classes_bp = Blueprint('classes', __name__, url_prefix='/turmas')

@classes_bp.route('/')
@login_required
@admin_required
def index():
    classes = Class.query.order_by(Class.name).all()
    return render_template('classes/index.html', classes=classes)

@classes_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    c = Class(
        name=request.form.get('name', '').strip(),
        description=request.form.get('description', '').strip() or None
    )
    db.session.add(c)
    db.session.commit()
    flash('Turma criada!', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(id):
    c = Class.query.get_or_404(id)
    c.name = request.form.get('name', c.name).strip()
    c.description = request.form.get('description', '').strip() or None
    db.session.commit()
    flash('Turma atualizada!', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    c = Class.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('Turma removida.', 'success')
    return redirect(url_for('classes.index'))

@classes_bp.route('/<int:id>/members', methods=['GET'])
@login_required
@admin_required
def members(id):
    c = Class.query.get_or_404(id)
    all_students = Student.query.order_by(Student.name).all()
    all_teachers = Teacher.query.order_by(Teacher.name).all()
    member_students = [s.id for s in c.students]
    member_teachers = [t.id for t in c.teachers]
    return render_template('classes/members.html',
        klass=c, all_students=all_students, all_teachers=all_teachers,
        member_students=member_students, member_teachers=member_teachers)

@classes_bp.route('/<int:id>/members', methods=['POST'])
@login_required
@admin_required
def save_members(id):
    c = Class.query.get_or_404(id)
    student_ids = request.form.getlist('student_ids', type=int)
    teacher_ids = request.form.getlist('teacher_ids', type=int)
    c.students = Student.query.filter(Student.id.in_(student_ids)).all() if student_ids else []
    c.teachers = Teacher.query.filter(Teacher.id.in_(teacher_ids)).all() if teacher_ids else []
    db.session.commit()
    flash('Membros atualizados!', 'success')
    return redirect(url_for('classes.index'))
