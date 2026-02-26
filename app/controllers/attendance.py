from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.klass import Class

attendance_bp = Blueprint('attendance', __name__, url_prefix='/presenca')

@attendance_bp.route('/')
@login_required
def index():
    lesson_id = request.args.get('lesson_id', type=int)

    if current_user.is_admin:
        available_lessons = Lesson.query.filter_by(status='LIBERADO').order_by(Lesson.date.desc()).all()
    else:
        from app.models.teacher import Teacher
        teacher = Teacher.query.filter_by(email=current_user.email).first()
        if teacher:
            class_ids = [c.id for c in teacher.classes]
            available_lessons = Lesson.query.filter(
                Lesson.status == 'LIBERADO',
                Lesson.class_id.in_(class_ids)
            ).order_by(Lesson.date.desc()).all()
        else:
            available_lessons = []

    selected_lesson = None
    attendances = []
    visitors = []

    if lesson_id:
        selected_lesson = Lesson.query.get(lesson_id)
        if selected_lesson:
            # Garante que TODOS os alunos da turma têm registro de presença
            # (resolve casos em que alunos foram adicionados após a geração das aulas)
            klass = selected_lesson.klass
            existing_ids = {
                a.student_id
                for a in Attendance.query.filter_by(lesson_id=lesson_id).all()
            }
            new_records = [
                Attendance(lesson_id=lesson_id, student_id=s.id, present=False)
                for s in klass.students
                if s.id not in existing_ids
            ]
            if new_records:
                db.session.add_all(new_records)
                db.session.commit()

            attendances = (
                Attendance.query
                .filter_by(lesson_id=lesson_id)
                .join(Attendance.student)
                .order_by(db.text('students.name'))
                .all()
            )
            visitors = Visitor.query.filter_by(lesson_id=lesson_id).all()

    return render_template('attendance/index.html',
        available_lessons=available_lessons,
        selected_lesson=selected_lesson,
        attendances=attendances,
        visitors=visitors,
        lesson_id=lesson_id
    )

@attendance_bp.route('/toggle', methods=['POST'])
@login_required
def toggle():
    lesson_id = request.form.get('lesson_id', type=int)
    student_id = request.form.get('student_id', type=int)
    att = Attendance.query.filter_by(lesson_id=lesson_id, student_id=student_id).first_or_404()
    att.present = not att.present
    db.session.commit()
    return jsonify({'present': att.present})

@attendance_bp.route('/mark-all', methods=['POST'])
@login_required
def mark_all():
    lesson_id = request.form.get('lesson_id', type=int)
    present = request.form.get('present') == 'true'
    Attendance.query.filter_by(lesson_id=lesson_id).update({'present': present})
    db.session.commit()
    return jsonify({'ok': True})

@attendance_bp.route('/offering', methods=['POST'])
@login_required
def offering():
    lesson_id = request.form.get('lesson_id', type=int)
    value = float(request.form.get('value', 0) or 0)
    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.offering = value
    db.session.commit()
    return jsonify({'ok': True})