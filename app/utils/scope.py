from flask_login import current_user
from app import db

def congregation_ids():
    return current_user.congregation_filter()

def scoped(model, congregation_field='congregation_id'):
    ids = congregation_ids()
    if not ids:
        return model.query.filter(db.false())
    return model.query.filter(getattr(model, congregation_field).in_(ids))

def scoped_class_ids():
    from app.models.klass import Class
    ids = congregation_ids()
    if not ids:
        return []
    return [c.id for c in Class.query.filter(Class.congregation_id.in_(ids)).all()]

def scoped_lessons():
    from app.models.lesson import Lesson
    cids = scoped_class_ids()
    if not cids:
        return Lesson.query.filter(db.false())
    return Lesson.query.filter(Lesson.class_id.in_(cids))
