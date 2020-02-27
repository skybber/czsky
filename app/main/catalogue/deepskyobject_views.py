import os

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db

from app.models import User, Catalogue, DeepskyObject, UserDsoDescription, UserDsoApertureDescription, SHOWN_APERTURE_DESCRIPTIONS
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name
from app.commons.search_utils import process_paginated_session_search

from .deepskyobject_forms import (
    DeepskyObjectFindChartForm,
    DeepskyObjectEditForm,
    SearchDsoForm,
)

from app.main.views import ITEMS_PER_PAGE
from .chart_generator import create_chart_in_pipeline, create_chart_by_extprocess
from app.commons.img_dir_resolver import resolve_img_path_dir, parse_inline_link


main_deepskyobject = Blueprint('main_deepskyobject', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 30/60, 1, 2, 5, 10)

@main_deepskyobject.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchDsoForm()

    page, search_expr, dso_type, catalogue, maglim = process_paginated_session_search('dso_search_page', [
        ('dso_search', search_form.q),
        ('dso_type', search_form.dso_type),
        ('dso_catal', search_form.catalogue),
        ('dso_maglim', search_form.maglim),
    ])

    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepskyObject.query
    if search_expr:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.name.like('%' + normalize_dso_name(search_expr) + '%'))

    mag_scale = (8, 16)

    if dso_type and dso_type != 'All':
        deepskyobjects = deepskyobjects.filter(DeepskyObject.type==dso_type)

    if catalogue and catalogue != 'All':
        cat_id = Catalogue.get_catalogue_id_by_cat_code(catalogue)
        if cat_id:
            deepskyobjects = deepskyobjects.filter_by(catalogue_id=cat_id)

    if not search_expr and maglim is not None and maglim < mag_scale[1]:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.v_mag<maglim)

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, mag_scale=mag_scale,
                           pagination=pagination, search_form=search_form)

@main_deepskyobject.route('/deepskyobject/search')
@login_required
def deepskyobject_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)
    normalized_name = normalize_dso_name(query)
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    if not dso:
        abort(404)
    return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.id))


@main_deepskyobject.route('/deepskyobject/<int:dso_id>')
@main_deepskyobject.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""

    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)

    sel_tab = request.args.get('sel_tab', None)
    if sel_tab:
        if sel_tab == 'fchart':
             return redirect(url_for('main_deepskyobject.deepskyobject_findchart', dso_id=dso.id))
        if sel_tab == 'aladin':
             return redirect(url_for('main_deepskyobject.deepskyobject_aladin', dso_id=dso.id))
        if sel_tab == 'catalogue_data':
             return redirect(url_for('main_deepskyobject.deepskyobject_catalogue_data', dso_id=dso.id))

    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    from_wishlist = request.args.get('from_wishlist')
    from_session_plan = request.args.get('from_session_plan')
    session_plan_id = request.args.get('session_plan_id')
    editor_user = User.get_editor_user()
    user_descr = None
    apert_descriptions = []
    if editor_user:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs').first()
        user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs') \
                        .filter(func.coalesce(UserDsoApertureDescription.text, '') != '') \
                        .order_by(UserDsoApertureDescription.aperture_class, UserDsoApertureDescription.lang_code)
        for apdescr in user_apert_descrs:
            if not apdescr.aperture_class in [cl[0] for cl in apert_descriptions] and apdescr.text:
                apert_descriptions.append((apdescr.aperture_class, apdescr.text),)

    prev_dso, next_dso = dso.get_prev_next_dso()
    editable=current_user.is_editor()
    descr_available = user_descr and user_descr.text or any([adescr for adescr in apert_descriptions])
    dso_image_info = _get_dso_image_info(dso.name, '')

    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, apert_descriptions=apert_descriptions,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id, from_wishlist = from_wishlist,
                           from_session_plan=from_session_plan, session_plan_id=session_plan_id,
                           prev_dso=prev_dso, next_dso=next_dso, editable=editable, descr_available=descr_available, dso_image_info=dso_image_info)

def _get_dso_image_info(dso_name, dir):
    dso_file_name = dso_name + '.jpg'
    img_dir_def = resolve_img_path_dir(os.path.join('dso', dso_file_name))
    if img_dir_def[0]:
        return img_dir_def[0] + 'dso/' + dso_file_name, parse_inline_link(img_dir_def[1])
    return None

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/aladin')
def deepskyobject_aladin(dso_id):
    """View a deepsky object in aladin."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    exact_ang_size = (3.0*dso.major_axis/60.0/60.0) if dso.major_axis else 1.0
    for i in range(len(ALADIN_ANG_SIZES)):
        if exact_ang_size < ALADIN_ANG_SIZES[i]:
            field_angular_size = ALADIN_ANG_SIZES[i]
            break
    else:
        field_angular_size = 10.0

    return render_template('main/catalogue/deepskyobject_info.html', type='aladin', dso=dso,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso, field_angular_size=field_angular_size)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object info."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/findchart', methods=['GET', 'POST'])
def deepskyobject_findchart(dso_id):
    """View a deepsky object findchart."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    form  = DeepskyObjectFindChartForm()
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    preview_url_dir = '/static/webassets-external/preview/'
    preview_dir = 'app' + preview_url_dir

    dso_dname = dso.denormalized_name().replace(' ','')

    field_sizes = (1, 3, 8, 20)
    fld_size = field_sizes[form.radius.data-1]

    prev_fld_size = session.get('prev_fld')
    session['prev_fld'] = fld_size

    night_mode = not session.get('themlight', False)

    mag_scales = [(12, 16), (10, 13), (8, 11), (6, 9)]
    cur_mag_scale = mag_scales[form.radius.data - 1]

    dso_mag_scales = [(10, 18), (10, 18), (7, 11), (7, 11)]
    cur_dso_mag_scale = dso_mag_scales[form.radius.data - 1]

    if prev_fld_size != fld_size:
        pref_maglim = session.get('pref_maglim' + str(fld_size))
        if pref_maglim is None:
            pref_maglim = (cur_mag_scale[0] + cur_mag_scale[1] + 1) // 2
        form.maglim.data = pref_maglim
        pref_dso_maglim = session.get('pref_dso_maglim' + str(fld_size))
        if pref_dso_maglim is None:
            pref_dso_maglim = (cur_dso_mag_scale[0] + cur_dso_mag_scale[1] + 1) // 2
        form.dso_maglim.data = pref_dso_maglim

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['pref_maglim'  + str(fld_size)] = form.maglim.data

    form.dso_maglim.data = _check_in_mag_interval(form.dso_maglim.data, cur_dso_mag_scale)
    session['pref_dso_maglim'  + str(fld_size)] = form.dso_maglim.data

    invert_part = '_i' if night_mode else ''
    mirror_x_part = '_mx' if form.mirror_x.data else ''
    mirror_y_part = '_my' if form.mirror_y.data else ''
    dso_file_name = dso_dname + '_' \
                + 'r' + str(fld_size) \
                + '_m' + str(form.maglim.data) \
                + '_dm' + str(form.dso_maglim.data) \
                + invert_part + mirror_x_part + mirror_y_part + '.png'

    full_file_name = os.path.join(preview_dir, dso_file_name)

    if not os.path.exists(full_file_name):
        create_chart_in_pipeline(dso_dname, full_file_name, fld_size, form.maglim.data, form.dso_maglim.data,
                                night_mode, form.mirror_x.data, form.mirror_y.data)

    fchart_url = preview_url_dir + dso_file_name

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    disable_dso_dec_mag = 'disabled' if form.dso_maglim.data <= cur_dso_mag_scale[0] else ''
    disable_dso_inc_mag = 'disabled' if form.dso_maglim.data >= cur_dso_mag_scale[1] else ''

    return render_template('main/catalogue/deepskyobject_info.html', form=form, type='fchart', dso=dso, fchart_url=fchart_url,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           dso_mag_scale=cur_dso_mag_scale, disable_dso_dec_mag=disable_dso_dec_mag, disable_dso_inc_mag=disable_dso_inc_mag,
                           show_mirroring=(form.radius.data<=2),
                           )

def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/edit', methods=['GET', 'POST'])
@login_required
def deepskyobject_edit(dso_id):
    """Update deepsky object."""
    if not current_user.is_editor():
        abort(403)
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    editor_user = User.get_editor_user()
    user_descr = None
    form = DeepskyObjectEditForm()
    goback = False
    if editor_user:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs').first()

        authors = {}

        if not user_descr:
            user_descr = UserDsoDescription(
                dso_id = dso_id,
                user_id = editor_user.id,
                rating = 5,
                lang_code = 'cs',
                common_name = '',
                text = '',
                references = '',
                cons_order = 1,
                create_by = current_user.id,
                create_date = datetime.now(),
                )

        all_user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs') \
                    .order_by(UserDsoApertureDescription.aperture_class)

        user_apert_descriptions = []
        # create missing UserDsoApertureDescription
        for aperture_class in SHOWN_APERTURE_DESCRIPTIONS:
            for ad in all_user_apert_descrs:
                if ad.aperture_class == aperture_class:
                    user_apert_descriptions.append(ad)
                    break
            else:
                ad = UserDsoApertureDescription(
                    dso_id = dso_id,
                    user_id = editor_user.id,
                    rating = 5,
                    lang_code = 'cs',
                    aperture_class = aperture_class,
                    text = '',
                    create_by = current_user.id,
                    create_date = datetime.now(),
                )
                user_apert_descriptions.append(ad)

        if request.method == 'GET':
            form.common_name.data = user_descr.common_name
            form.text.data = user_descr.text
            form.references.data = user_descr.references
            for ad in user_apert_descriptions:
                adi = form.aperture_descr_items.append_entry()
                adi.aperture_class.data = ad.aperture_class
                adi.text.data = ad.text
                adi.is_public.data = ad.is_public
                adi.text.label = ad.aperture_class
        elif form.validate_on_submit():
            was_text_changed = user_descr.text != form.text.data
            if was_text_changed or user_descr.common_name != form.common_name.data or user_descr.references != form.references.data :
                user_descr.common_name = form.common_name.data
                user_descr.references = form.references.data
                user_descr.text = form.text.data
                if was_text_changed:
                    user_descr.update_by = current_user.id
                    user_descr.update_date = datetime.now()
                db.session.add(user_descr)
            for adi in form.aperture_descr_items:
                for ad in user_apert_descriptions:
                    if ad.aperture_class == adi.aperture_class.data:
                        if ad.text != adi.text.data:
                            ad.text = adi.text.data
                            ad.is_public = adi.is_public.data
                            ad.update_by = current_user.id
                            ad.update_date = datetime.now()
                            db.session.add(ad)
            db.session.commit()

            flash('Deepsky object successfully updated', 'form-success')

            if form.goback.data == 'true':
                goback = True

    authors['dso'] = _create_author_entry(user_descr.update_by, user_descr.update_date)
    for ad in user_apert_descriptions:
        authors[ad.aperture_class] = _create_author_entry(ad.update_by, ad.update_date)

    from_constellation_id = request.args.get('from_constellation_id')

    if goback:
        if from_constellation_id is not None:
            return redirect(url_for('main_constellation.constellation_info', constellation_id=from_constellation_id, _anchor='dso' + str(dso.id)))
        return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.id))

    return render_template('main/catalogue/deepskyobject_edit.html', form=form, dso=dso,
                           from_constellation_id=from_constellation_id, authors=authors,
                           )

def _create_author_entry(update_by, update_date):
    if update_by is None:
        return ('', '')
    user_name = User.query.filter_by(id=update_by).first().user_name
    return (user_name, update_date.strftime("%Y-%m-%d %H:%M"))

def _filter_apert_descriptions(all_user_apert_descrs):
    apert_descriptions = []
    for apdescr in all_user_apert_descrs:
        if not apdescr.aperture_class in [cl[0] for cl in apert_descriptions]:
            apert_descriptions.append((apdescr.aperture_class, apdescr.text),)
    return apert_descriptions

