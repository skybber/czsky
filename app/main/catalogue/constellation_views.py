from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Constellation, UserConsDescription, UserDsoDescription, UserStarDescription, UserDsoApertureDescription, DeepskyObject, WishList, ObservedList
from app.commons.search_utils import process_session_search

from app.commons.auto_img_utils import get_dso_image_info, get_dso_image_info_with_imgdir, get_ug_bl_dsos
from app.commons.utils import get_cs_editor_user, get_lang_and_editor_user_from_request

from .constellation_forms import (
    ConstellationEditForm,
    SearchConstellationForm,
)

main_constellation = Blueprint('main_constellation', __name__)

@main_constellation.route('/constellations', methods=['GET', 'POST'])
def constellations():
    """View all constellations."""

    search_form = SearchConstellationForm()

    if not process_session_search([('const_search', search_form.q), ('const_season', search_form.season)]):
        return redirect(url_for('main_constellation.constellations'))

    lang, editor_user = get_lang_and_editor_user_from_request()
    constellations = Constellation.query
    if search_form.q.data:
        constellations = constellations.filter(Constellation.name.like('%' + search_form.q.data + '%'))

    if editor_user:
        db_common_names = UserConsDescription.query \
                    .with_entities(UserConsDescription.constellation_id, UserConsDescription.common_name) \
                    .filter_by(user_id=editor_user.id, lang_code=lang)
    else:
        db_common_names = []

    if search_form.season.data and search_form.season.data != 'All':
        constellations = constellations.filter(Constellation.season==search_form.season.data)

    cons_names = { i[0] : i[1] for i in db_common_names }

    return render_template('main/catalogue/constellations.html', constellations=constellations, search_form=search_form, cons_names=cons_names)

def _find_constellation(constellation_id):
    try:
        int_id = int(constellation_id)
        return Constellation.query.filter_by(id=int_id).first()
    except ValueError:
        pass
    return Constellation.query.filter_by(iau_code=constellation_id).first()

@main_constellation.route('/constellation/<string:constellation_id>')
@main_constellation.route('/constellation/<string:constellation_id>/info')
def constellation_info(constellation_id):
    """View a constellation info."""
    constellation = _find_constellation(constellation_id)
    if constellation is None:
        abort(404)
    user_descr = None
    common_name = None
    dso_descriptions = None
    star_descriptions = None
    title_images = None
    ug_bl_dsos = None
    lang, editor_user = get_lang_and_editor_user_from_request()
    cs_editor_user = get_cs_editor_user()

    if editor_user:
        ucd = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=editor_user.id, lang_code=lang)\
                .first()

        user_descr = ucd.text if ucd else None
        common_name = ucd.common_name if ucd else None

        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code=lang)\
                .filter_by(constellation_id=constellation.id) \
                .all()
        star_descriptions = _sort_star_descr(star_descriptions)

        all_cs_dso_descriptions = UserDsoDescription.query.filter_by(user_id=cs_editor_user.id, lang_code='cs')\
                .join(UserDsoDescription.deepskyObject, aliased=True) \
                .filter(DeepskyObject.constellation_id==constellation.id, DeepskyObject.type!='AST') \
                .order_by(UserDsoDescription.rating.desc(), DeepskyObject.mag) \
                .all()

        if lang != 'cs':
            # Show all objects that are in CS version plus UG-BL objects
            existing = set(dsod.dso_id for dsod in all_cs_dso_descriptions)
            all_dso_descriptions = []
            available_dso_descriptions = UserDsoDescription.query.filter_by(user_id=editor_user.id, lang_code=lang)\
                    .join(UserDsoDescription.deepskyObject, aliased=True) \
                    .filter(DeepskyObject.constellation_id==constellation.id, DeepskyObject.type!='AST') \
                    .order_by(UserDsoDescription.rating.desc(), DeepskyObject.mag) \
                    .all()

            available_dso_descriptions_map = {}

            for dsod in available_dso_descriptions:
                available_dso_descriptions_map[dsod.dso_id] = dsod
                if dsod.dso_id in existing:
                    all_dso_descriptions.append(dsod)
                elif dsod.deepskyObject.mag<10.0:
                    all_dso_descriptions.append(dsod)
                    existing.add(dsod.dso_id)

            constell_ug_bl_dsos = get_ug_bl_dsos()[constellation.id]
            for dso_id in constell_ug_bl_dsos:
                dso = constell_ug_bl_dsos[dso_id]
                loading_dso_id = dso.master_id if dso.master_id is not None else dso_id
                if not dso_id in existing and loading_dso_id in available_dso_descriptions_map:
                    all_dso_descriptions.append(available_dso_descriptions_map[loading_dso_id])

        else:
            all_dso_descriptions = all_cs_dso_descriptions

        existing = set()
        dso_descriptions = []
        title_images = {}
        for dsod in all_dso_descriptions:
            if not dsod.dso_id in existing:
                existing.add(dsod.dso_id)
                dso_descriptions.append(dsod)
            if not dsod.text or not dsod.text.startswith('![<]($IMG_DIR/'):
                image_info = get_dso_image_info_with_imgdir(dsod.deepskyObject.normalized_name_for_img())
                if image_info is not None:
                    title_images[dsod.dso_id] = image_info[0]

        dso_apert_descriptions = UserDsoApertureDescription.query.filter_by(user_id=editor_user.id, lang_code=lang)\
                .join(UserDsoApertureDescription.deepskyObject, aliased=True) \
                .filter_by(constellation_id=constellation.id) \
                .order_by(UserDsoApertureDescription.aperture_class, UserDsoApertureDescription.lang_code) \
                .all()

        aperture_descr_map = {}
        for apdescr in dso_apert_descriptions:
            if not apdescr.dso_id in aperture_descr_map:
                aperture_descr_map[apdescr.dso_id] = []
            dsoapd = aperture_descr_map[apdescr.dso_id]
            if not apdescr.aperture_class in [cl[0] for cl in dsoapd]:
                dsoapd.append((apdescr.aperture_class, apdescr.text),)

        ug_bl_dsos = []
        constell_ug_bl_dsos = get_ug_bl_dsos()[constellation.id]
        for dso_id in constell_ug_bl_dsos:
            if not dso_id in existing:
                dso = constell_ug_bl_dsos[dso_id]
                if not dso.master_id in existing:
                    dso_image_info = get_dso_image_info(dso.normalized_name_for_img())
                    ug_bl_dsos.append({ 'dso': dso, 'img_info': dso_image_info })

        ug_bl_dsos.sort(key=lambda x: x['dso'].mag)
    editable=current_user.is_editor()

    wish_list = None
    observed_list = None
    if current_user.is_authenticated:
        wish_list = [ item.dso_id for item in WishList.create_get_wishlist_by_user_id(current_user.id).wish_list_items ]
        observed_list = [ item.dso_id for item in ObservedList.create_get_observed_list_by_user_id(current_user.id).observed_list_items ]

    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info',
                           user_descr=user_descr, common_name = common_name, star_descriptions=star_descriptions,
                           dso_descriptions=dso_descriptions, aperture_descr_map=aperture_descr_map, editable=editable,
                           ug_bl_dsos=ug_bl_dsos, wish_list=wish_list, observed_list=observed_list, title_images=title_images,
                           )

@main_constellation.route('/constellation/<int:constellation_id>/edit', methods=['GET', 'POST'])
@login_required
def constellation_edit(constellation_id):
    """Update constellation."""
    if not current_user.is_editor():
        abort(403)
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)

    lang, editor_user = get_lang_and_editor_user_from_request()
    user_descr = None
    form = ConstellationEditForm()
    goback = False
    if editor_user:
        user_descr = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=editor_user.id, lang_code=lang).first()
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
        return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.iau_code))

    author = _create_author_entry(user_descr.update_by, user_descr.update_date)

    return render_template('main/catalogue/constellation_edit.html', form=form, constellation=constellation,
                           user_descr=user_descr, author=author)

def _create_author_entry(update_by, update_date):
    if update_by is None:
        return ('', '')
    user_name = User.query.filter_by(id=update_by).first().user_name
    return (user_name, update_date.strftime("%Y-%m-%d %H:%M"))

@main_constellation.route('/constellation/<string:constellation_id>/stars')
def constellation_stars(constellation_id):
    """View a constellation stars."""
    constellation = _find_constellation(constellation_id)
    if constellation is None:
        abort(404)
    star_descriptions = None
    editable=current_user.is_editor()
    lang, editor_user = get_lang_and_editor_user_from_request()

    aster_descriptions = None
    if editor_user:
        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code = lang)\
                .filter_by(constellation_id=constellation.id) \
                .all()
        star_descriptions = _sort_star_descr(star_descriptions)

        all_aster_descriptions = UserDsoDescription.query.filter_by(user_id=editor_user.id, lang_code=lang)\
                .join(UserDsoDescription.deepskyObject, aliased=True) \
                .filter(DeepskyObject.constellation_id==constellation.id, DeepskyObject.type=='AST') \
                .order_by(UserDsoDescription.rating.desc()) \
                .all()

        existing = set()
        aster_descriptions = []
        for dsod in all_aster_descriptions:
            if not dsod.dso_id in existing:
                existing.add(dsod.dso_id)
                aster_descriptions.append(dsod)

    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='stars',
                           star_descriptions=star_descriptions, aster_descriptions=aster_descriptions, editable=editable)


@main_constellation.route('/constellation/<string:constellation_id>/deepskyobjects')
def constellation_deepskyobjects(constellation_id):
    """View a constellation deep sky objects."""
    constellation = _find_constellation(constellation_id)
    if constellation is None:
        abort(404)
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='dso')


def _sort_star_descr(star_descriptions):
    return sorted(star_descriptions, key=lambda a: a.star.mag if a.star and a.star.mag else 100.0)


