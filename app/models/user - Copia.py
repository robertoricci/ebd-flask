from app import db, login_manager
from flask_login import UserMixin
import bcrypt
from datetime import datetime

# Roles:
#   SUPERADMIN  → acesso total, gerencia igrejas e congregações
#   CHURCH_ADMIN → gerencia todas as congregações de uma igreja
#   ADMIN       → gerencia sua congregação
#   TEACHER     → acessa presença da sua congregação

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    email           = db.Column(db.String(150), unique=True, nullable=False)
    password_hash   = db.Column(db.String(255), nullable=False)
    role            = db.Column(db.String(20), default='TEACHER')
    active          = db.Column(db.Boolean, default=True)
    church_id       = db.Column(db.Integer, db.ForeignKey('churches.id',       ondelete='SET NULL'), nullable=True)
    congregation_id = db.Column(db.Integer, db.ForeignKey('congregations.id',  ondelete='SET NULL'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    church       = db.relationship('Church',       foreign_keys=[church_id],       lazy='joined')
    congregation = db.relationship('Congregation', foreign_keys=[congregation_id], lazy='joined')

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    @property
    def is_superadmin(self):
        return self.role == 'SUPERADMIN'

    @property
    def is_church_admin(self):
        return self.role == 'CHURCH_ADMIN'

    @property
    def is_admin(self):
        return self.role in ('SUPERADMIN', 'CHURCH_ADMIN', 'ADMIN')

    @property
    def is_congregation_admin(self):
        return self.role == 'ADMIN'

    def can_see_congregation(self, congregation_id):
        if self.is_superadmin:
            return True
        if self.is_church_admin:
            from app.models.church import Congregation
            c = Congregation.query.get(congregation_id)
            return c and c.church_id == self.church_id
        return self.congregation_id == congregation_id

    def congregation_filter(self):
        """Retorna lista de congregation_ids visíveis para este user."""
        if self.is_superadmin:
            from app.models.church import Congregation
            return [c.id for c in Congregation.query.all()]
        if self.is_church_admin:
            from app.models.church import Congregation
            return [c.id for c in Congregation.query.filter_by(church_id=self.church_id).all()]
        return [self.congregation_id] if self.congregation_id else []

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
