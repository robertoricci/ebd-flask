from functools import wraps
from flask import abort
from flask_login import current_user

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """ADMIN, CHURCH_ADMIN ou SUPERADMIN."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

def church_admin_required(f):
    """CHURCH_ADMIN ou SUPERADMIN."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_superadmin or current_user.is_church_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated
