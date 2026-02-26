from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

    # Render fornece DATABASE_URL com prefixo "postgres://" (antigo),
    # SQLAlchemy 2.x exige "postgresql+psycopg://" para o driver psycopg3
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///ebd.db')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    from app.models import user, teacher, student, klass, trimester, lesson, attendance, visitor
    from app.controllers.auth import auth_bp
    from app.controllers.dashboard import dashboard_bp
    from app.controllers.users import users_bp
    from app.controllers.teachers import teachers_bp
    from app.controllers.students import students_bp
    from app.controllers.classes import classes_bp
    from app.controllers.trimesters import trimesters_bp
    from app.controllers.lessons import lessons_bp
    from app.controllers.attendance import attendance_bp
    from app.controllers.visitors import visitors_bp
    from app.controllers.reports import reports_bp
    from app.controllers.birthdays import birthdays_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(teachers_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(trimesters_bp)
    app.register_blueprint(lessons_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(visitors_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(birthdays_bp)

    from app import template_filters
    template_filters.register(app)

    return app
