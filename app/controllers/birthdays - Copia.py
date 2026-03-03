from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models.teacher import Teacher
from app.models.student import Student
from sqlalchemy import func
from app import db
from datetime import date

birthdays_bp = Blueprint('birthdays', __name__, url_prefix='/aniversarios')

@birthdays_bp.route('/')
@login_required
def index():
    month = request.args.get('month', type=int, default=date.today().month)
    teachers = Teacher.query.filter(
        Teacher.birth_date.isnot(None),
        func.extract('month', Teacher.birth_date) == month
    ).order_by(func.extract('day', Teacher.birth_date)).all()
    students = Student.query.filter(
        Student.birth_date.isnot(None),
        func.extract('month', Student.birth_date) == month
    ).order_by(func.extract('day', Student.birth_date)).all()

    people = []
    today = date.today()
    for t in teachers:
        age = today.year - t.birth_date.year
        is_today = t.birth_date.month == today.month and t.birth_date.day == today.day
        people.append({'name': t.name, 'type': 'Professor', 'birth_date': t.birth_date, 'age': age, 'is_today': is_today})
    for s in students:
        age = today.year - s.birth_date.year
        is_today = s.birth_date.month == today.month and s.birth_date.day == today.day
        people.append({'name': s.name, 'type': 'Aluno', 'birth_date': s.birth_date, 'age': age, 'is_today': is_today})

    people.sort(key=lambda x: x['birth_date'].day)

    months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
              'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    return render_template('birthdays/index.html', people=people, month=month, months=months)
