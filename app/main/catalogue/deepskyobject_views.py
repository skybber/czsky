import os

from datetime import datetime
from io import BytesIO

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
    jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db

from app.models import User, Catalogue, DeepskyObject, UserDsoDescription, DsoList, UserDsoApertureDescription, WishList, WishListItem, ObservedList, ObservedListItem, SHOWN_APERTURE_DESCRIPTIONS
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
from app.commons.search_utils import process_paginated_session_search
from app.commons.utils import to_float, to_boolean

from .deepskyobject_forms import (
    DeepskyObjectFindChartForm,
    DeepskyObjectEditForm,
    SearchDsoForm,
)

from app.main.views import ITEMS_PER_PAGE
from app.commons.chart_generator import create_chart, create_chart_legend, MAX_IMG_WIDTH, MAX_IMG_HEIGHT
from app.commons.img_dir_resolver import resolve_img_path_dir, parse_inline_link

main_deepskyobject = Blueprint('main_deepskyobject', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 15/60, 30/60, 1, 2, 5, 10)

FIELD_SIZES = (1, 2, 5, 10, 20, 40, 60, 80)
    
GUI_FIELD_SIZES = []

for i in range(0, len(FIELD_SIZES)-1):
    GUI_FIELD_SIZES.append(FIELD_SIZES[i])
    GUI_FIELD_SIZES.append((FIELD_SIZES[i] + FIELD_SIZES[i+1]) / 2)
    
GUI_FIELD_SIZES.append(FIELD_SIZES[-1])

# DEFAULT_MAG = [15, 12, 11, (8, 11), (6, 9), (6, 8), 6, 6, 5]
MAG_SCALES = [(12, 16), (11, 15), (10, 13), (8, 11), (6, 9), (6, 8), (5, 7), (5, 7)]
DSO_MAG_SCALES = [(10, 18), (10, 18), (10, 18), (7, 15), (7, 13), (6, 11), (5, 10), (5, 9)]

@main_deepskyobject.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchDsoForm()

    ret, page = process_paginated_session_search('dso_search_page', [
        ('dso_search', search_form.q),
        ('dso_type', search_form.dso_type),
        ('dso_catal', search_form.catalogue),
        ('dso_maglim', search_form.maglim),
    ])
    
    if not ret:
        return redirect(url_for('main_deepskyobject.deepskyobjects'))

    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepskyObject.query
    if search_form.q.data:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.name.like('%' + normalize_dso_name(search_form.q.data) + '%'))

    mag_scale = (8, 16)

    if search_form.dso_type.data and search_form.dso_type.data != 'All':
        deepskyobjects = deepskyobjects.filter(DeepskyObject.type==search_form.dso_type.data)

    if search_form.catalogue.data and search_form.catalogue.data != 'All':
        cat_id = Catalogue.get_catalogue_id_by_cat_code(search_form.catalogue.data)
        if cat_id:
            deepskyobjects = deepskyobjects.filter_by(catalogue_id=cat_id)

    if not search_form.q.data and search_form.maglim.data is not None and search_form.maglim.data < mag_scale[1]:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.mag<search_form.maglim.data)

    deepskyobjects_for_render = deepskyobjects.order_by(DeepskyObject.id).limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, mag_scale=mag_scale,
                           pagination=pagination, search_form=search_form)


@main_deepskyobject.route('/deepskyobject/search')
def deepskyobject_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)
    normalized_name = normalize_dso_name(denormalize_dso_name(query))
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    if not dso:
        abort(404)
    return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name))


def _find_dso(dso_id):
    try:
        int_id = int(dso_id)
        dso = DeepskyObject.query.filter_by(id=int_id).first()
    except ValueError:
        dso = DeepskyObject.query.filter_by(name=dso_id).first()
    orig_dso = dso
    if dso and dso.master_id:
        dso = DeepskyObject.query.filter_by(id=dso.master_id).first()
    return dso, orig_dso


def _get_other_names(master_dso):
    child_dsos = DeepskyObject.query.filter_by(master_id=master_dso.id)
    return ' / '.join(dso.name for dso in child_dsos)


@main_deepskyobject.route('/deepskyobject/switch-wish-list', methods=['GET'])
@login_required
def deepskyobject_switch_wish_list():
    dso_id = request.args.get('dso_id', None, type=int)
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    wish_list_item = WishListItem.query.filter_by(wish_list_id=wish_list.id, dso_id=dso_id).first()
    if wish_list_item:
        db.session.delete(wish_list_item)
        result = 'off'
    else:
        wish_list.append_new_deepsky_object(dso_id, current_user.id)
        result = 'on'
    return jsonify(result=result)


@main_deepskyobject.route('/deepskyobject/switch-observed-list', methods=['GET'])
@login_required
def deepskyobject_switch_observed_list():
    dso_id = request.args.get('dso_id', None, type=int)
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    observed_list_item = ObservedListItem.query.filter_by(observed_list_id=observed_list.id, dso_id=dso_id).first()
    if observed_list_item:
        db.session.delete(observed_list_item)
        result = 'off'
    else:
        observed_list.append_new_deepsky_object(dso_id, current_user.id)
        result = 'on'
    return jsonify(result=result)


@main_deepskyobject.route('/deepskyobject/<string:dso_id>')
@main_deepskyobject.route('/deepskyobject/<string:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    sel_tab = request.args.get('sel_tab', None)
    if sel_tab:
        if sel_tab == 'fchart':
            return _do_redirect('main_deepskyobject.deepskyobject_fchart', dso)
        if sel_tab == 'surveys':
            return _do_redirect('main_deepskyobject.deepskyobject_surveys', dso)
        if sel_tab == 'catalogue_data':
            return _do_redirect('main_deepskyobject.deepskyobject_catalogue_data', dso)

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

    prev_dso, prev_dso_title, next_dso, next_dso_title = _get_prev_next_dso(orig_dso)
    editable=current_user.is_editor()
    descr_available = user_descr and user_descr.text or any([adescr for adescr in apert_descriptions])
    dso_image_info = _get_dso_image_info(dso.normalized_name_for_img(), '')

    other_names = _get_other_names(dso)
    
    wish_list = None
    observed_list = None
    if current_user.is_authenticated:
        wish_item = WishListItem.query.filter(WishListItem.dso_id.in_((dso.id, orig_dso.id))) \
            .join(WishList) \
            .filter(WishList.user_id==current_user.id) \
            .first()
        wish_list = [wish_item.dso_id] if wish_item is not None else []
        
        observed_item = ObservedListItem.query.filter(ObservedListItem.dso_id.in_((dso.id, orig_dso.id))) \
            .join(ObservedList) \
            .filter(ObservedList.user_id==current_user.id) \
            .first()
        observed_list = [observed_item.dso_id] if observed_item is not None else []
        
    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, apert_descriptions=apert_descriptions,
                           prev_dso=prev_dso, next_dso=next_dso, prev_dso_title=prev_dso_title, next_dso_title=next_dso_title,
                           editable=editable, descr_available=descr_available, dso_image_info=dso_image_info, other_names=other_names, 
                           wish_list=wish_list, observed_list=observed_list,
                           )


def _get_dso_image_info(dso_name, dir):
    dso_file_name = dso_name + '.jpg'
    img_dir_def = resolve_img_path_dir(os.path.join('dso', dso_file_name))
    if img_dir_def[0]:
        return img_dir_def[0] + 'dso/' + dso_file_name, parse_inline_link(img_dir_def[1])
    return None


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/surveys', methods=['GET', 'POST'])
def deepskyobject_surveys(dso_id):
    """Digital surveys view a deepsky object."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    prev_dso, prev_dso_title, next_dso, next_dso_title = _get_prev_next_dso(orig_dso)
    exact_ang_size = (3.0*dso.major_axis/60.0/60.0) if dso.major_axis else 1.0

    field_size = _get_survey_field_size(ALADIN_ANG_SIZES, exact_ang_size, 10.0)

    return render_template('main/catalogue/deepskyobject_info.html', type='surveys', dso=dso,
                           prev_dso=prev_dso, next_dso=next_dso, prev_dso_title=prev_dso_title, next_dso_title=next_dso_title, field_size=field_size,
                           )


def _get_survey_field_size(ang_sizes, exact_ang_size, default_size):
    for i in range(len(ang_sizes)):
        if exact_ang_size < ang_sizes[i]:
            return ang_sizes[i]
    return default_size


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object info."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    prev_dso, prev_dso_title, next_dso, next_dso_title = _get_prev_next_dso(orig_dso)
    
    other_names = _get_other_names(dso)
    
    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           prev_dso=prev_dso, next_dso=next_dso, prev_dso_title=prev_dso_title, next_dso_title=next_dso_title, other_names=other_names,
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/fchart', methods=['GET', 'POST'])
def deepskyobject_fchart(dso_id):
    """View a deepsky object findchart."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    form  = DeepskyObjectFindChartForm()
    prev_dso, prev_dso_title, next_dso, next_dso_title = _get_prev_next_dso(orig_dso)

    fld_size = FIELD_SIZES[form.radius.data-1]
    
    prev_fld_size = session.get('prev_fld')
    session['prev_fld'] = fld_size

    night_mode = not session.get('themlight', False)

    cur_mag_scale = MAG_SCALES[form.radius.data - 1]
    cur_dso_mag_scale = DSO_MAG_SCALES[form.radius.data - 1]

    if prev_fld_size != fld_size or request.method == 'GET':
        _, pref_maglim, pref_dso_maglim = _get_fld_size_maglim(form.radius.data-1)
        form.maglim.data = pref_maglim
        form.dso_maglim.data = pref_dso_maglim
        
    mag_range_values = []
    dso_mag_range_values = []
    
    for i in range(0, len(FIELD_SIZES)):
        _, ml, dml = _get_fld_size_maglim(i)
        mag_range_values.append(ml)
        dso_mag_range_values.append(dml)
        
    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['pref_maglim'  + str(fld_size)] = form.maglim.data

    form.dso_maglim.data = _check_in_mag_interval(form.dso_maglim.data, cur_dso_mag_scale)
    session['pref_dso_maglim'  + str(fld_size)] = form.dso_maglim.data

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    disable_dso_dec_mag = 'disabled' if form.dso_maglim.data <= cur_dso_mag_scale[0] else ''
    disable_dso_inc_mag = 'disabled' if form.dso_maglim.data >= cur_dso_mag_scale[1] else ''
    
    gui_field_sizes = ','.join(str(x) for x in GUI_FIELD_SIZES)
    
    if form.ra.data is None:
        form.ra.data = dso.ra 
    if form.dec.data is None:
        form.dec.data = dso.dec 
        
    return render_template('main/catalogue/deepskyobject_info.html', form=form, type='fchart', dso=dso, 
                           prev_dso=prev_dso, next_dso=next_dso, prev_dso_title=prev_dso_title, next_dso_title=next_dso_title,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           dso_mag_scale=cur_dso_mag_scale, disable_dso_dec_mag=disable_dso_dec_mag, disable_dso_inc_mag=disable_dso_inc_mag,
                           gui_field_sizes=gui_field_sizes, gui_field_index = (form.radius.data-1)*2, 
                           chart_fsz=str(fld_size), chart_mlim=str(form.maglim.data), chart_dlim=str(form.dso_maglim.data), chart_nm=('1' if night_mode else '0'), 
                           chart_mx=('1' if form.mirror_x.data else '0'), chart_my=('1' if form.mirror_y.data else '0'),
                           mag_ranges=MAG_SCALES, mag_range_values=mag_range_values, dso_mag_ranges=DSO_MAG_SCALES, dso_mag_range_values=dso_mag_range_values, 
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/fchart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def deepskyobject_fchart_pos_img(dso_id, ra, dec):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()
   
    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)
    
    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT
    
    night_mode = to_boolean(request.args.get('nm'), True) 
    mirror_x = to_boolean(request.args.get('mx'), False)
    mirror_y = to_boolean(request.args.get('my'), False)
    
    img_bytes = BytesIO()
    create_chart(img_bytes, float(ra), float(dec), gui_fld_size, width, height, maglim, dso_maglim, night_mode, mirror_x, mirror_y, show_legend=False, dso_names=(dso.name,))
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')

@main_deepskyobject.route('/deepskyobject/<string:dso_id>/fchart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def deepskyobject_fchart_legend_img(dso_id, ra, dec):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    
    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()
    
    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)
    
    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT
        
    night_mode = to_boolean(request.args.get('nm'), True) 
    mirror_x = to_boolean(request.args.get('mx'), False)
    mirror_y = to_boolean(request.args.get('my'), False)
    
    img_bytes = BytesIO()
    create_chart_legend(img_bytes, float(ra), float(dec), width, height, gui_fld_size, maglim, dso_maglim, night_mode, mirror_x, mirror_y)
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')


def _get_fld_size_maglim(fld_size_index):
    fld_size = FIELD_SIZES[fld_size_index]
        
    mag_scale = MAG_SCALES[fld_size_index]
    dso_mag_scale = DSO_MAG_SCALES[fld_size_index]
    
    maglim = session.get('pref_maglim' + str(fld_size))
    if maglim is None:
        maglim = (mag_scale[0] + mag_scale[1] + 1) // 2
        
    dso_maglim = session.get('pref_dso_maglim' + str(fld_size))
    if dso_maglim is None:
        dso_maglim = (dso_mag_scale[0] + dso_mag_scale[1] + 1) // 2
        
    return (fld_size, maglim, dso_maglim)


def _get_fld_size_mags_from_request():
    gui_fld_size = to_float(request.args.get('fsz'), 20.0)
    
    for i in range(len(FIELD_SIZES)-1, -1, -1):
        if gui_fld_size >= FIELD_SIZES[i]:
            fld_size_index = i
            break
    else:
        fld_size_index = 0
    
    fld_size, maglim, dso_maglim = _get_fld_size_maglim(fld_size_index)
    
    if gui_fld_size > fld_size and (fld_size_index + 1) < len(FIELD_SIZES):
        next_fld_size, next_maglim, next_dso_maglim = _get_fld_size_maglim(fld_size_index+1)
        maglim = (maglim + next_maglim) / 2
        dso_maglim = (dso_maglim + next_dso_maglim) / 2
    
    return (gui_fld_size, maglim, dso_maglim)

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
                rating = form.rating.data,
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
                    rating = 1,
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
            form.rating.data = user_descr.rating
            for ad in user_apert_descriptions:
                adi = form.aperture_descr_items.append_entry()
                adi.aperture_class.data = ad.aperture_class
                adi.text.data = ad.text
                adi.is_public.data = ad.is_public
                adi.text.label = ad.aperture_class
        elif form.validate_on_submit():
            was_text_changed = user_descr.text != form.text.data
            if was_text_changed or user_descr.common_name != form.common_name.data or \
               user_descr.references != form.references.data or user_descr.rating != form.rating.data:
                user_descr.common_name = form.common_name.data
                user_descr.references = form.references.data
                user_descr.text = form.text.data
                user_descr.rating = form.rating.data
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

    if goback:
        back = request.args.get('back')
        back_id = request.args.get('back_id')
        if back == 'constellation':
            return redirect(url_for('main_constellation.constellation_info', constellation_id=back_id, _anchor='dso' + str(dso.id)))
        return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back=back, back_id=back_id))

    return render_template('main/catalogue/deepskyobject_edit.html', form=form, dso=dso, authors=authors, is_new=False)


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


def _do_redirect(url, dso):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    return redirect(url_for(url, dso_id=dso.id, back=back, back_id=back_id))


def _get_prev_next_dso(dso):
    back = request.args.get('back')
    back_id = request.args.get('back_id')

    if back == 'observation':
        pass # TODO
    elif back == 'wishlist':
        pass # TODO
    elif back == 'observed_list':
        if current_user.is_authenticated:
            observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
            prev_item, next_item = observed_list.get_prev_next_item(dso.id)
            return (prev_item.deepskyObject if prev_item else None,
                    prev_item.deepskyObject.denormalized_name() if prev_item else None,
                    next_item.deepskyObject if next_item else None,
                    next_item.deepskyObject.denormalized_name() if next_item else None,
                    )
    elif back == 'session_plan':
        pass # TODO
    elif back == 'dso_list' and not (back_id is None):
        dso_list = DsoList.query.filter_by(name=back_id).first()
        if dso_list:
            prev_item, next_item = dso_list.get_prev_next_item(dso.id)
            return (prev_item.deepskyObject if prev_item else None,
                    prev_item.item_id if prev_item else None,
                    next_item.deepskyObject if next_item else None,
                    next_item.item_id if next_item else None,
                    )
              
    prev_dso, next_dso = dso.get_prev_next_dso()
    return (prev_dso,
            prev_dso.catalog_number() if prev_dso else None,
            next_dso,
            next_dso.catalog_number() if next_dso else None)
