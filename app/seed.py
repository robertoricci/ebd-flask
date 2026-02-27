from app import create_app, db
from app.models.user import User
from app.models.church import Church, Congregation

app = create_app()

with app.app_context():
    # Criar superadmin se não existir
    if not User.query.filter_by(email='super@ebd.com').first():
        # Igreja padrão
        church = Church.query.first()
        if not church:
            church = Church(name='Igreja Padrão', city='São Paulo', state='SP')
            db.session.add(church)
            db.session.flush()

        # Congregação padrão
        cong = Congregation.query.first()
        if not cong:
            cong = Congregation(name='Congregação Central', church_id=church.id, city='São Paulo')
            db.session.add(cong)
            db.session.flush()

        # SuperAdmin
        su = User(name='Super Admin', email='super@ebd.com', role='SUPERADMIN')
        su.set_password('super@123')
        db.session.add(su)

        # Admin padrão vinculado à congregação
        if not User.query.filter_by(email='admin@ebd.com').first():
            admin = User(name='Administrador', email='admin@ebd.com', role='ADMIN',
                        congregation_id=cong.id, church_id=church.id)
            admin.set_password('admin@123')
            db.session.add(admin)

        db.session.commit()
        print('✅ SuperAdmin criado: super@ebd.com / super@123')
        print('✅ Admin criado: admin@ebd.com / admin@123')
    else:
        print('ℹ️  SuperAdmin já existe.')
