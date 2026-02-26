from app import create_app, db
from app.models.user import User

app = create_app()
with app.app_context():
    if not User.query.filter_by(email='admin@ebd.com').first():
        u = User(name='Administrador', email='admin@ebd.com', role='ADMIN')
        u.set_password('admin123')
        db.session.add(u)
        db.session.commit()
        print('✅ Admin criado: admin@ebd.com / admin123')
    else:
        print('ℹ️ Admin já existe.')
