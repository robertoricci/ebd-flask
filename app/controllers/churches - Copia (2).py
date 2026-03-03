from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models.church import Church, Congregation
from app.utils.decorators import superadmin_required

churches_bp = Blueprint('churches', __name__, url_prefix='/igrejas')

@churches_bp.route('/')
@login_required
@superadmin_required
def index():
    churches = Church.query.order_by(Church.name).all()
    return render_template('churches/index.html', churches=churches)

@churches_bp.route('/create', methods=['POST'])
@login_required
@superadmin_required
def create():
    c = Church(
        name=request.form.get('name','').strip(),
        city=request.form.get('city','').strip() or None,
        state=request.form.get('state','').strip() or None,
        app_title=request.form.get('app_title','').strip() or None,
        app_subtitle=request.form.get('app_subtitle','').strip() or None,
    )
    db.session.add(c); db.session.commit()
    flash('Igreja criada!', 'success')
    return redirect(url_for('churches.index'))

@churches_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@superadmin_required
def edit(id):
    c = Church.query.get_or_404(id)
    c.name        = request.form.get('name', c.name).strip()
    c.city        = request.form.get('city','').strip() or None
    c.state       = request.form.get('state','').strip() or None
    c.app_title   = request.form.get('app_title','').strip() or None
    c.app_subtitle= request.form.get('app_subtitle','').strip() or None
    db.session.commit()
    flash('Igreja atualizada!', 'success')
    return redirect(url_for('churches.index'))

@churches_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete(id):
    c = Church.query.get_or_404(id)
    db.session.delete(c); db.session.commit()
    flash('Igreja removida.', 'success')
    return redirect(url_for('churches.index'))

@churches_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def toggle(id):
    c = Church.query.get_or_404(id)
    c.active = not c.active
    db.session.commit()
    return jsonify({'active': c.active})

# ── Congregações ──────────────────────────────────────────────────────────

@churches_bp.route('/<int:church_id>/congregacoes')
@login_required
@superadmin_required
def congregations(church_id):
    church = Church.query.get_or_404(church_id)
    congs  = Congregation.query.filter_by(church_id=church_id).order_by(Congregation.name).all()
    return render_template('churches/congregations.html', church=church, congregations=congs)

@churches_bp.route('/<int:church_id>/congregacoes/create', methods=['POST'])
@login_required
@superadmin_required
def create_congregation(church_id):
    Church.query.get_or_404(church_id)
    cong = Congregation(
        name=request.form.get('name','').strip(),
        city=request.form.get('city','').strip() or None,
        address=request.form.get('address','').strip() or None,
        church_id=church_id,
    )
    db.session.add(cong); db.session.commit()
    flash('Congregação criada!', 'success')
    return redirect(url_for('churches.congregations', church_id=church_id))

@churches_bp.route('/congregacoes/<int:id>/edit', methods=['POST'])
@login_required
@superadmin_required
def edit_congregation(id):
    cong = Congregation.query.get_or_404(id)
    cong.name    = request.form.get('name', cong.name).strip()
    cong.city    = request.form.get('city','').strip() or None
    cong.address = request.form.get('address','').strip() or None
    db.session.commit()
    flash('Congregação atualizada!', 'success')
    return redirect(url_for('churches.congregations', church_id=cong.church_id))

@churches_bp.route('/congregacoes/<int:id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_congregation(id):
    cong = Congregation.query.get_or_404(id)
    church_id = cong.church_id
    db.session.delete(cong); db.session.commit()
    flash('Congregação removida.', 'success')
    return redirect(url_for('churches.congregations', church_id=church_id))
