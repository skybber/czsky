from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Constellation, UserConsDescription, UserDsoDescription, UserStarDescription, UserDsoApertureDescription
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
    editor_user = User.get_editor_user()
    constellations = Constellation.query
    if search_expr:
        constellations = constellations.filter(Constellation.name.like('%' + search_expr + '%'))

    if editor_user:
        db_common_names = UserConsDescription.query \
                    .with_entities(UserConsDescription.constellation_id, UserConsDescription.common_name) \
                    .filter_by(user_id=editor_user.id, lang_code='cs')
    else:
        db_common_names = []

    if season and season != 'All':
        constellations = constellations.filter(Constellation.season==season)

    cons_names = { i[0] : i[1] for i in db_common_names }

    return render_template('main/catalogue/constellations.html', constellations=constellations, search_form=search_form, cons_names=cons_names)

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
    editor_user = User.get_editor_user()
    if editor_user:
        ud = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=editor_user.id, lang_code='cs')\
                .first()

        user_descr = ud.text if ud else None

        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
                .filter_by(constellation_id=constellation.id) \
                .all()

        all_dso_descriptions = UserDsoDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
                .join(UserDsoDescription.deepskyObject, aliased=True) \
                .filter_by(constellation_id=constellation.id) \
                .all()

        existing = set()
        dso_descriptions = []
        for dsod in all_dso_descriptions:
            if not dsod.dso_id in existing:
                existing.add(dsod.dso_id)
                dso_descriptions.append(dsod)

        dso_apert_descriptions = UserDsoApertureDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
                .join(UserDsoApertureDescription.deepskyObject, aliased=True) \
                .filter_by(constellation_id=constellation.id) \
                .all()

        aperture_descr_map = {}
        for apdescr in dso_apert_descriptions:
            if not apdescr.dso_id in aperture_descr_map:
                aperture_descr_map[apdescr.dso_id] = []
            dsoapd = aperture_descr_map[apdescr.dso_id]
            if not apdescr.aperture_class in [cl[0] for cl in dsoapd]:
                dsoapd.append((apdescr.aperture_class, apdescr.text),)

    editable=current_user.is_editor()
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info',
                           user_descr=user_descr, star_descriptions=star_descriptions, dso_descriptions=dso_descriptions,
                           aperture_descr_map=aperture_descr_map, editable=editable)

@main_constellation.route('/constellation/<int:constellation_id>/edit', methods=['GET', 'POST'])
@login_required
def constellation_edit(constellation_id):
    """Update deepsky object."""
    if not current_user.is_editor():
        abort(403)
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)

    editor_user = User.get_editor_user()
    user_descr = None
    form = ConstellationEditForm()
    goback = False
    if editor_user:
        user_descr = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=editor_user.id, lang_code='cs').first()
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
            if form.goback.data == 'true':
                goback = True

    if goback:
        return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.id))

    author = _create_author_entry(user_descr.update_by, user_descr.update_date)

    return render_template('main/catalogue/constellation_edit.html', form=form, constellation=constellation,
                           user_descr=user_descr, author=author)

def _create_author_entry(update_by, update_date):
    if update_by is None:
        return ('', '')
    user_name = User.query.filter_by(id=update_by).first().user_name
    return (user_name, update_date.strftime("%Y-%m-%d %H:%M"))

@main_constellation.route('/constellation/<int:constellation_id>/stars')
def constellation_stars(constellation_id):
    """View a constellation stars."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    star_descriptions = None
    editable=current_user.is_editor()
    editor_user = User.get_editor_user()
    if editor_user:
        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code = 'cs')\
                .filter_by(constellation_id=constellation.id) \
                .all()

    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='stars',
                           star_descriptions=star_descriptions, editable=editable)


@main_constellation.route('/constellation/<int:constellation_id>/deepskyobjects')
def constellation_deepskyobjects(constellation_id):
    """View a constellation deep sky objects."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='dso')
