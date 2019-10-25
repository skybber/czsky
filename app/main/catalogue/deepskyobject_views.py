import os
import subprocess

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Catalogue, DeepskyObject, Permission, UserDsoDescription
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name
from app.commons.search_utils import process_paginated_session_search

from .deepskyobject_forms import (
    DeepskyObjectEditForm,
    SearchDsoForm,
)

from app.main.views import ITEMS_PER_PAGE

main_deepskyobject = Blueprint('main_deepskyobject', __name__)

@main_deepskyobject.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchDsoForm()

    page, search_expr, dso_type, catalogue = process_paginated_session_search('dso_search_page', [
        ('dso_search', search_form.q),
        ('dso_type', search_form.dso_type),
        ('dso_catal', search_form.catalogue),
    ])

    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepskyObject.query
    if search_expr:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.name.like('%' + normalize_dso_name(search_expr) + '%'))

    if dso_type and dso_type != 'All':
        deepskyobjects = deepskyobjects.filter(DeepskyObject.type==dso_type)

    if catalogue and catalogue != 'All':
        cat_id = Catalogue.get_catalogue_id_by_cat_code(catalogue)
        if cat_id:
            deepskyobjects = deepskyobjects.filter_by(catalogue_id=cat_id)

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, pagination=pagination, search_form=search_form)


@main_deepskyobject.route('/deepskyobject/<int:dso_id>')
@main_deepskyobject.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    user_8mag = User.query.filter_by(email='8mag').first()
    user_descr = None
    if user_8mag:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_8mag.id) \
                        .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .first()
    prev_dso, next_dso = dso.get_prev_next_dso()
    editable=current_user.can(Permission.EDIT_COMMON_CONTENT)
    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, from_constellation_id=from_constellation_id,
                           prev_dso=prev_dso, next_dso=next_dso, editable=editable)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object info."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           from_constellation_id=from_constellation_id, prev_dso=prev_dso, next_dso=next_dso)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/findchart')
def deepskyobject_findchart(dso_id):
    """View a deepsky object findchart."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    preview_url_dir = '/static/webassets-external/preview/'
    preview_dir = 'app' + preview_url_dir
    dso_dname = dso.denormalized_name().replace(' ','')
    pdf_file =  preview_dir + dso_dname + '.pdf'
    if not os.path.exists(pdf_file):
        p = subprocess.Popen(['fchart', '-O', 'pdf', '-o', preview_dir, dso_dname])
        p.wait()
    fchart = preview_url_dir + dso_dname + '.pdf'
    return render_template('main/catalogue/deepskyobject_info.html', type='fchart', dso=dso, fchart=fchart,
                           from_constellation_id=from_constellation_id, prev_dso=prev_dso, next_dso=next_dso)


@main_deepskyobject.route('/deepskyobject/<int:dso_id>/edit', methods=['GET', 'POST'])
@login_required
def deepskyobject_edit(dso_id):
    """Update deepsky object."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    if not current_user.can(Permission.EDIT_COMMON_CONTENT):
        abort(403)

    user_8mag = User.query.filter_by(email='8mag').first()
    user_descr = None
    form = DeepskyObjectEditForm()
    if user_8mag:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_8mag.id) \
                        .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .first()
        if request.method == 'GET':
            form.common_name.data = user_descr.common_name
            form.text.data = user_descr.text
        elif form.validate_on_submit():
            user_descr.common_name = form.common_name.data
            user_descr.text = form.text.data
            user_descr.update_by = current_user.id
            user_descr.update_date = datetime.now()
            db.session.add(user_descr)
            db.session.commit()
            flash('Observation successfully updated', 'form-success')

    from_constellation_id = request.args.get('from_constellation_id')

    return render_template('main/catalogue/deepskyobject_edit.html', form=form, dso=dso, user_descr=user_descr, from_constellation_id=from_constellation_id)
