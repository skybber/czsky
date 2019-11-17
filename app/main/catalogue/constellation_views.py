from datetime import datetime

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Constellation, Permission, UserConsDescription, UserDsoDescription, UserStarDescription
from app.commons.search_utils import process_session_search

from .constellation_forms import (
    ConstellationEditForm,
    SearchConstellationForm,
)

main_constellation = Blueprint('main_constellation', __name__)

@main_constellation.route('/constellations', methods=['GET', 'POST'])
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

@main_constellation.route('/constellation/<int:constellation_id>')
@main_constellation.route('/constellation/<int:constellation_id>/info')
def constellation_info(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    user_descr = None
    dso_descriptions = None
    star_descriptions = None
    user_8mag = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    if user_8mag:
        ud = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=user_8mag.id)\
                .filter(UserConsDescription.lang_code.in_(('cs', 'sk'))) \
                .order_by(UserConsDescription.lang_code) \
                .first()

        user_descr = ud.text if ud else None

        star_descriptions = UserStarDescription.query.filter_by(user_id=user_8mag.id, lang_code = 'cs')\
                .order_by(UserStarDescription.lang_code) \
                .filter_by(constellation_id=constellation.id) \
                .all()

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

    editable=current_user.is_editor()
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info',
                           user_descr=user_descr, star_descriptions=star_descriptions, dso_descriptions=dso_descriptions, editable=editable)

@main_constellation.route('/constellation/<int:constellation_id>/edit', methods=['GET', 'POST'])
@login_required
def constellation_edit(constellation_id):
    """Update deepsky object."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    if not current_user.is_editor():
        abort(403)

    user_8mag = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
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

@main_constellation.route('/constellation/<int:constellation_id>/stars')
def constellation_stars(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='stars')


@main_constellation.route('/constellation/<int:constellation_id>/deepskyobjects')
def constellation_deepskyobjects(constellation_id):
    """View a constellation deep sky objects."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='dso')
