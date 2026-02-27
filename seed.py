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

    if not User.query.filter_by(email='ricci@ebd.com').first():
        u = User(name='ricci', email='ricci@ebd.com', role='PROFESSOR')
        u.set_password('ricci123')
        db.session.add(u)
        db.session.commit()
        print('✅ Admin criado: admin@ebd.com / admin123')
    else:
        print('ℹ️ Admin já existe.')
   
   
    if not User.query.filter_by(email='carlos@ebd.com').first():
        u = User(name='carlos', email='carlos@ebd.com', role='PROFESSOR')
        u.set_password('carlos123')
        db.session.add(u)
        db.session.commit()
        print('✅ carlos criado: carlos@ebd.com / carlos123')
    else:
        print('ℹ️ Admin já existe.')