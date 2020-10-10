from datetime import datetime

import glob, os

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

from app.models import User, Constellation, UserConsDescription, UserDsoDescription, UserStarDescription, UserDsoApertureDescription, DeepskyObject, WishList
from app.commons.search_utils import process_session_search

from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
from app.commons.img_dir_resolver import resolve_img_path_dir, parse_inline_link

from .constellation_forms import (
    ConstellationEditForm,
    SearchConstellationForm,
)

main_constellation = Blueprint('main_constellation', __name__)

_ug_bl_dsos = None

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
    ug_bl_dsos = None
    editor_user = User.get_editor_user()
    if editor_user:
        ucd = UserConsDescription.query.filter_by(constellation_id=constellation.id, user_id=editor_user.id, lang_code='cs')\
                .first()

        user_descr = ucd.text if ucd else None
        common_name = ucd.common_name if ucd else None

        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
                .filter_by(constellation_id=constellation.id) \
                .all()
        star_descriptions = _sort_star_descr(star_descriptions)

        all_dso_descriptions = UserDsoDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
                .join(UserDsoDescription.deepskyObject, aliased=True) \
                .filter(DeepskyObject.constellation_id==constellation.id, DeepskyObject.type!='AST') \
                .order_by(UserDsoDescription.rating.desc()) \
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
                .order_by(UserDsoApertureDescription.aperture_class, UserDsoApertureDescription.lang_code) \
                .all()

        aperture_descr_map = {}
        for apdescr in dso_apert_descriptions:
            if not apdescr.dso_id in aperture_descr_map:
                aperture_descr_map[apdescr.dso_id] = []
            dsoapd = aperture_descr_map[apdescr.dso_id]
            if not apdescr.aperture_class in [cl[0] for cl in dsoapd]:
                dsoapd.append((apdescr.aperture_class, apdescr.text),)

        all_ug_bl_dsos = _get_ug_bl_dsos()
        ug_bl_dsos = []
        if constellation.id in all_ug_bl_dsos:
            constell_ug_bl_dsos = all_ug_bl_dsos[constellation.id]
            for dso_id in constell_ug_bl_dsos:
                if not dso_id in existing:
                    dso = constell_ug_bl_dsos[dso_id]
                    if not dso.master_id in existing:
                        dso_image_info = _get_dso_image_info(dso.normalized_name_for_img(), '')
                        ug_bl_dsos.append({ 'dso': dso, 'img_info': dso_image_info })
        ug_bl_dsos.sort(key=lambda x: x['dso'].mag)
    editable=current_user.is_editor()
    
    wish_list = None
    if current_user.is_authenticated:
        wish_list = [ item.dso_id for item in WishList.create_get_wishlist_by_user_id(current_user.id).sky_list.sky_list_items ]
    
    return render_template('main/catalogue/constellation_info.html', constellation=constellation, type='info',
                           user_descr=user_descr, common_name = common_name, star_descriptions=star_descriptions,
                           dso_descriptions=dso_descriptions, aperture_descr_map=aperture_descr_map, editable=editable,
                           ug_bl_dsos=ug_bl_dsos, wish_list=wish_list)

@main_constellation.route('/constellation/<int:constellation_id>/edit', methods=['GET', 'POST'])
@login_required
def constellation_edit(constellation_id):
    """Update constellation."""
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
    editor_user = User.get_editor_user()
    
    aster_descriptions = None
    if editor_user:
        star_descriptions = UserStarDescription.query.filter_by(user_id=editor_user.id, lang_code = 'cs')\
                .filter_by(constellation_id=constellation.id) \
                .all()
        star_descriptions = _sort_star_descr(star_descriptions)

        all_aster_descriptions = UserDsoDescription.query.filter_by(user_id=editor_user.id, lang_code='cs')\
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


def _get_dso_image_info(dso_name, dir):
    dso_file_name = dso_name + '.jpg'
    img_dir_def = resolve_img_path_dir(os.path.join('dso', dso_file_name))
    if img_dir_def[0]:
        return img_dir_def[0] + 'dso/' + dso_file_name, parse_inline_link(img_dir_def[1])
    return None

def _get_ug_bl_dsos():
    global _ug_bl_dsos
    if not _ug_bl_dsos:
        ug_bl_dsos = {}
        files = [f for f in sorted(glob.glob('app/static/webassets-external/users/glahn/img/dso/*.jpg'))] + \
            [f for f in sorted(glob.glob('app/static/webassets-external/users/laville/img/dso/*.jpg'))]

        for f in files:
            base_name = os.path.basename(f)
            if base_name.endswith('.jpg'):
                dso_name = base_name[:-len('.jpg')]
                normalized_name = normalize_dso_name(denormalize_dso_name(dso_name))
                dso = DeepskyObject.query.filter_by(name=normalized_name).first()
                if dso:
                    db.session.expunge(dso)
                    if not dso.constellation_id in ug_bl_dsos:
                        ug_bl_dsos[dso.constellation_id] = {}
                    ug_bl_dsos[dso.constellation_id][dso.id] = dso

        _ug_bl_dsos = ug_bl_dsos
    return _ug_bl_dsos

def _sort_star_descr(star_descriptions):
    return sorted(star_descriptions, key=lambda a: a.star.mag if a.star and a.star.mag else 100.0)


