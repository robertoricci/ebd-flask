from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app import db
from app.models.lesson import Lesson
from app.models.attendance import Attendance
from app.models.visitor import Visitor
from app.models.trimester import Trimester
from app.models.klass import Class
from app.models.student import Student
from app.models.teacher import Teacher
from datetime import date
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    trimesters = Trimester.query.order_by(Trimester.year.desc(), Trimester.quarter.desc()).all()
    classes = Class.query.order_by(Class.name).all()
    
    trimester_id = request.args.get('trimester_id', type=int)
    filter_date = request.args.get('date', '')
    class_id = request.args.get('class_id', type=int)

    q = Lesson.query
    if trimester_id:
        q = q.filter_by(trimester_id=trimester_id)
    if filter_date:
        try:
            from datetime import datetime
            fd = datetime.strptime(filter_date, '%Y-%m-%d').date()
            q = q.filter_by(date=fd)
        except:
            pass
    if class_id:
        q = q.filter_by(class_id=class_id)

    lessons = q.all()
    lesson_ids = [l.id for l in lessons]

    total_students = Student.query.count()
    total_teachers = Teacher.query.count()
    total_classes = Class.query.count()
    total_lessons = len(lessons)

    att_q = Attendance.query.filter(Attendance.lesson_id.in_(lesson_ids)) if lesson_ids else Attendance.query.filter(db.false())
    total_present = att_q.filter_by(present=True).count() if lesson_ids else 0
    total_absent = att_q.filter_by(present=False).count() if lesson_ids else 0
    total_visitors = Visitor.query.filter(Visitor.lesson_id.in_(lesson_ids)).count() if lesson_ids else 0
    total_offering = db.session.query(func.sum(Lesson.offering)).filter(Lesson.id.in_(lesson_ids)).scalar() or 0

    freq_pct = round((total_present / (total_present + total_absent)) * 100, 1) if (total_present + total_absent) > 0 else 0

    today = date.today()
    today_lessons = Lesson.query.filter_by(date=today).all()

    # Birthdays this month
    month = today.month
    from app.models.teacher import Teacher as T
    from app.models.student import Student as S
    birthday_teachers = T.query.filter(
        func.extract('month', T.birth_date) == month
    ).all() if True else []
    birthday_students = S.query.filter(
        func.extract('month', S.birth_date) == month
    ).all() if True else []
    birthdays = [{'name': t.name, 'type': 'Professor', 'birth_date': t.birth_date} for t in birthday_teachers] + \
                [{'name': s.name, 'type': 'Aluno', 'birth_date': s.birth_date} for s in birthday_students]
    birthdays.sort(key=lambda x: x['birth_date'].day if x['birth_date'] else 0)

    return render_template('dashboard/index.html',
        trimesters=trimesters, classes=classes,
        trimester_id=trimester_id, filter_date=filter_date, class_id=class_id,
        total_students=total_students, total_teachers=total_teachers,
        total_classes=total_classes, total_lessons=total_lessons,
        total_present=total_present, total_absent=total_absent,
        total_visitors=total_visitors, total_offering=total_offering,
        freq_pct=freq_pct, today_lessons=today_lessons, birthdays=birthdays
    )
