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

    sel_tab = request.args.get('sel_tab', None)
    if sel_tab:
        if sel_tab == 'fchart':
             return redirect(url_for('main_deepskyobject.deepskyobject_findchart', dso_id=dso.id))
        if sel_tab == 'catalogue_data':
             return redirect(url_for('main_deepskyobject.deepskyobject_catalogue_data', dso_id=dso.id))

    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    editor_user = User.get_editor_user()
    user_descr = None
    apert_descriptions = []
    if editor_user:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs').first()
        user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code='cs') \
                        .filter(func.coalesce(UserDsoApertureDescription.text, '') != '') \
                        .order_by(UserDsoApertureDescription.aperture_class, UserDsoApertureDescription.lang_code)
        for apdescr in user_apert_descrs:
            if not apdescr.aperture_class in [cl[0] for cl in apert_descriptions]:
                apert_descriptions.append((apdescr.aperture_class, apdescr.text),)

    prev_dso, next_dso = dso.get_prev_next_dso()
    editable=current_user.is_editor()
    descr_available = user_descr or len(apert_descriptions)>0
    dso_image = None
    if not descr_available:
        dso_image = _get_dso_image(dso.name, '')
        if not dso_image:
            dso_image = _get_dso_image(dso.name, 'ngcic')

    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, apert_descriptions=apert_descriptions,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso, editable=editable, descr_available=descr_available, dso_image=dso_image)

def _get_dso_image(dso_name, dir):
    full_dso_file_name = 'app' + os.path.join(current_app.config.get('IMG_DIR'), 'dso', dir, dso_name + '.jpg')
    if os.path.exists(full_dso_file_name):
        sep = '/' if dir else ''
        return current_app.config.get('IMG_DIR') + 'dso/' + dir + sep + dso_name + '.jpg'
    return None

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
