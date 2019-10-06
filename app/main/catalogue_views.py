from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Constellation, DeepSkyObject, UserConsDescription, UserDsoDescription
from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.dso_utils import normalize_dso_name

from .forms import (
    SearchForm,
)

from .views import ITEMS_PER_PAGE

main_catalogue = Blueprint('main_catalogue', __name__)

@main_catalogue.route('/constellations')
def constellations():
    """View all constellations."""
    constellations = Constellation.query.all()
    return render_template(
        'main/catalogue/constellations.html', constellations=constellations)


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

    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info', user_descr=user_descr, dso_descriptions=dso_descriptions)


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
    search_form = SearchForm()

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepSkyObject.query
    search = False
    if search_form.q.data:
        deepskyobjects = deepskyobjects.filter(DeepSkyObject.name.like('%' + normalize_dso_name(search_form.q.data) + '%'))
        search = True

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=search, record_name='deepskyobjects', css_framework='semantic')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, pagination=pagination, search_form=search_form)


@main_catalogue.route('/deepskyobject/<int:dso_id>')
@main_catalogue.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, from_constellation_id=from_constellation_id)

@main_catalogue.route('/deepskyobject/<int:dso_id>')
@main_catalogue.route('/deepskyobject/<int:dso_id>/descr')
def deepskyobject_descr(dso_id):
    """View a deepsky object info."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    user_8mag = User.query.filter_by(email='8mag').first()
    dso_description = None
    if user_8mag:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_8mag.id).filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .join(DeepSkyObject) \
                        .filter_by(id=dso.id) \
                        .first()
    return render_template('main/catalogue/deepskyobject_info.html', type='descr', dso=dso, user_descr=user_descr, from_constellation_id=from_constellation_id)

