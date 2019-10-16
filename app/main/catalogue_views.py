import os
import subprocess

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Catalogue, Constellation, DeepSkyObject, Permission, UserConsDescription, UserDsoDescription
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name,get_prev_next_dso
from app.commons.search_utils import process_paginated_session_search, process_session_search

from .forms import (
    ConstellationEditForm,
    DeepskyObjectEditForm,
    SearchConstellationForm,
    SearchDsoForm,
)

from .views import ITEMS_PER_PAGE

main_catalogue = Blueprint('main_catalogue', __name__)

@main_catalogue.route('/constellations', methods=['GET', 'POST'])
def constellations():
    """View all constellations."""
    search_form = SearchConstellationForm()

    search_expr, season = process_session_search([('const_search', search_form.q), ('const_season', search_form.season)])

    constellations = Constellation.query
    if search_expr:
        constellations = constellations.filter(Constellation.name.like('%' + search_expr + '%'))

    if season and season != 'All':
        constellations = constellations.filter(Constellation.season==season)

    return render_template('main/catalogue/constellations.html', constellations=constellations, search_form=search_form)

@main_catalogue.route('/constellation/<int:constellation_id>')
@main_catalogue.route('/constellation/<int:constellation_id>/info')
def constellation_info(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    user_descr = None
    dso_descriptions = None
    user_8mag = User.query.filter_by(email='8mag').first()
    if user_8mag:
        ud = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=user_8mag.id)\
                .filter(UserConsDescription.lang_code.in_(('cs', 'sk'))) \
                .order_by(UserConsDescription.lang_code) \
                .first()

        user_descr = ud.text if ud else None

        all_dso_descriptions = UserDsoDescription.query.filter_by(user_id=user_8mag.id)\
                .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                .order_by(UserDsoDescription.lang_code) \
                .join(UserDsoDescription.deepSkyObject, aliased=True) \
                .filter_by(constellation_id=constellation.id) \
                .all()

        existing = set()
        dso_descriptions = []
        for dsod in all_dso_descriptions:
            if not dsod.dso_id in existing:
                existing.add(dsod.dso_id)
                dso_descriptions.append(dsod)

    editable=current_user.can(Permission.EDIT_COMMON_CONTENT)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info',
                           user_descr=user_descr, dso_descriptions=dso_descriptions, editable=editable)

@main_catalogue.route('/constellation/<int:constellation_id>/edit', methods=['GET', 'POST'])
@login_required
def constellation_edit(constellation_id):
    """Update deepsky object."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    if not current_user.can(Permission.EDIT_COMMON_CONTENT):
        abort(403)

    user_8mag = User.query.filter_by(email='8mag').first()
    user_descr = None
    form = ConstellationEditForm()
    if user_8mag:
        user_descr = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=user_8mag.id) \
                        .filter(UserConsDescription.lang_code.in_(('cs', 'sk'))) \
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
            flash('Constellation successfully updated', 'form-success')

    return render_template('main/catalogue/constellation_edit.html', form=form, constellation=constellation, user_descr=user_descr)

@main_catalogue.route('/constellation/<int:constellation_id>/stars')
def constellation_stars(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='stars')


@main_catalogue.route('/constellation/<int:constellation_id>/deepskyobjects')
def constellation_deepskyobjects(constellation_id):
    """View a constellation deep sky objects."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='dso')

@main_catalogue.route('/deepskyobjects', methods=['GET', 'POST'])
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

    deepskyobjects = DeepSkyObject.query
    if search_expr:
        deepskyobjects = deepskyobjects.filter(DeepSkyObject.name.like('%' + normalize_dso_name(search_expr) + '%'))

    if dso_type and dso_type != 'All':
        deepskyobjects = deepskyobjects.filter(DeepSkyObject.type==dso_type)

    if catalogue and catalogue != 'All':
        cat_id = Catalogue.get_catalogue_id(catalogue)
        if cat_id:
            deepskyobjects = deepskyobjects.filter_by(catalogue_id=cat_id)

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, pagination=pagination, search_form=search_form)


@main_catalogue.route('/deepskyobject/<int:dso_id>')
@main_catalogue.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    user_8mag = User.query.filter_by(email='8mag').first()
    user_descr = None
    if user_8mag:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_8mag.id) \
                        .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .first()
    prev_dso, next_dso = get_prev_next_dso(dso)
    editable=current_user.can(Permission.EDIT_COMMON_CONTENT)
    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, from_constellation_id=from_constellation_id,
                           prev_dso=prev_dso, next_dso=next_dso, editable=editable)

@main_catalogue.route('/deepskyobject/<int:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object info."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    prev_dso, next_dso = get_prev_next_dso(dso)
    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           from_constellation_id=from_constellation_id, prev_dso=prev_dso, next_dso=next_dso)

@main_catalogue.route('/deepskyobject/<int:dso_id>/findchart')
def deepskyobject_findchart(dso_id):
    """View a deepsky object findchart."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    prev_dso, next_dso = get_prev_next_dso(dso)
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


@main_catalogue.route('/deepskyobject/<int:dso_id>/edit', methods=['GET', 'POST'])
@login_required
def deepskyobject_edit(dso_id):
    """Update deepsky object."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
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
