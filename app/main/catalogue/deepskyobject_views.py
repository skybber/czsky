import os
import numpy as np
import base64
import urllib.parse

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.sql.expression import literal

from app import db

from app.models import (
    Catalogue,
    Constellation,
    DeepskyObject,
    dso_observation_association_table,
    ObservingSession,
    DsoList,
    Observation,
    ObservedList,
    ObservedListItem,
    ObsSessionPlanRun,
    ObservationTargetType,
    SHOWN_APERTURE_DESCRIPTIONS,
    SessionPlan,
    SessionPlanItem,
    SessionPlanItemType,
    User,
    UserDsoApertureDescription,
    UserDsoDescription,
    WishList,
    WishListItem,
)
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
from app.commons.search_utils import process_paginated_session_search, get_items_per_page, create_table_sort
from app.commons.utils import get_lang_and_editor_user_from_request
from app.commons.permission_utils import allow_view_session_plan

from .deepskyobject_forms import (
    DeepskyObjectEditForm,
    DeepskyObjectObservationLogForm,
    SearchDsoForm,
)

from app.main.chart.chart_forms import ChartForm

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
)

from app.commons.auto_img_utils import get_dso_image_info, get_dso_image_info_with_imgdir
from app.commons.prevnext_utils import create_prev_next_wrappers
from app.commons.highlights_list_utils import create_hightlights_lists

main_deepskyobject = Blueprint('main_deepskyobject', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 15/60, 30/60, 1, 2, 5, 10)

DSO_TABLE_COLUMNS = [ 'name', 'type', 'ra', 'dec', 'constellation', 'mag', 'size' ]


@main_deepskyobject.route('/dso-menu', methods=['GET'])
def dso_menu():
    return render_template('main/catalogue/dso_menu.html')


@main_deepskyobject.route('/all-deepskyobjects', methods=['GET', 'POST'])
def all_deepskyobjects():
    session.pop('dso_search', None)
    session.pop('dso_type', None)
    session.pop('dso_catal', None)
    session.pop('dso_maglim', None)
    session.pop('dec_min', None)
    session.pop('dso_max_axis_ratio', None)
    session.pop('dso_sort_by', None)
    return redirect(url_for('main_deepskyobject.deepskyobjects'))


@main_deepskyobject.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchDsoForm()

    sort_def = { 'name': DeepskyObject.name,
                 'type': DeepskyObject.type,
                 'ra': DeepskyObject.ra,
                 'dec': DeepskyObject.dec,
                 'constellation': DeepskyObject.constellation_id,
                 'mag': DeepskyObject.mag,
                 'major_axis': DeepskyObject.major_axis,
                 }

    if request.method == 'GET' or search_form.validate_on_submit():
        ret, page, sort_by = process_paginated_session_search('dso_search_page', 'dso_sort_by', [
            ('dso_search', search_form.q),
            ('dso_type', search_form.dso_type),
            ('dso_catal', search_form.catalogue),
            ('dso_maglim', search_form.maglim),
            ('dec_min', search_form.dec_min),
            ('max_axis_ratio', search_form.max_axis_ratio),
            ('items_per_page', search_form.items_per_page)
        ])

        if not ret:
            return redirect(url_for('main_deepskyobject.deepskyobjects', page=page, sortby=sort_by))

        table_sort = create_table_sort(sort_by, sort_def.keys())

        if search_form.maglim.data is None:
            search_form.maglim.data = search_form.maglim.default

        per_page = get_items_per_page(search_form.items_per_page)

        offset = (page - 1) * per_page

        dso_query = DeepskyObject.query
        if search_form.q.data:
            dso_query = dso_query.filter_by(name=normalize_dso_name(search_form.q.data))
        else:
            if search_form.dso_type.data and search_form.dso_type.data != 'All':
                dso_query = dso_query.filter(DeepskyObject.type == search_form.dso_type.data)
            cat_id = None
            if search_form.catalogue.data and search_form.catalogue.data != 'All':
                cat_id = Catalogue.get_catalogue_id_by_cat_code(search_form.catalogue.data)
                if cat_id:
                    dso_query = dso_query.filter_by(catalogue_id=cat_id)

            if not cat_id:
                dso_query = dso_query.filter_by(master_id=None)

            if search_form.dec_min.data:
                dso_query = dso_query.filter(DeepskyObject.dec > (np.pi * search_form.dec_min.data / 180.0))

            if search_form.max_axis_ratio.data:
                dso_query = dso_query.filter(DeepskyObject.axis_ratio <= search_form.max_axis_ratio.data)

            if search_form.maglim.data:
                dso_query = dso_query.filter(DeepskyObject.mag <= search_form.maglim.data)

        order_by_field = None
        if sort_by:
            desc = sort_by[0] == '-'
            sort_by_name = sort_by[1:] if desc else sort_by
            order_by_field = sort_def.get(sort_by_name)
            if order_by_field and desc:
                order_by_field = order_by_field.desc()

        if order_by_field is None:
            order_by_field = DeepskyObject.id

        shown_dsos = dso_query.order_by(order_by_field).limit(per_page).offset(offset).all()

        observed = set()
        if not current_user.is_anonymous:
            for dso in ObservedList.get_observed_dsos_by_user_id(current_user.id):
                observed.add(dso.id)

        pagination = Pagination(page=page, per_page=per_page, total=dso_query.count(), search=False, record_name='deepskyobjects',
                                css_framework='semantic', not_passed_args='back')
    else:
        table_sort = create_table_sort(request.args.get('sortby'), sort_def.keys())
        shown_dsos = []
        pagination = None
        observed = None

    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=shown_dsos, pagination=pagination, search_form=search_form,
                           table_sort=table_sort, observed=observed)


@main_deepskyobject.route('/deepskyobject/search')
def deepskyobject_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)
    if query and query.isdigit():
        query = 'NGC' + query
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
        dso_id = urllib.parse.unquote(dso_id)
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
        db.session.commit()
        result = 'off'
    else:
        wish_list_item = wish_list.create_new_deepsky_object_item(dso_id)
        db.session.add(wish_list_item)
        db.session.commit()
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
        db.session.commit()
        result = 'off'
    else:
        observed_list_item = observed_list.create_new_deepsky_object_item(dso_id)
        db.session.add(observed_list_item)
        db.session.commit()
        result = 'on'
    return jsonify(result=result)


@main_deepskyobject.route('/deepskyobject/switch-session-plan', methods=['GET'])
def deepskyobject_switch_session_plan():
    dso_id = request.args.get('dso_id', None, type=int)
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    session_plan_id = request.args.get('session_plan_id', None, type=int)
    if not session_plan_id:
        abort(404)
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if not session_plan:
        abort(404)

    if current_user.is_anonymous:
        if not session_plan.is_anonymous or session.get('session_plan_id') != session_plan.id:
            abort(404)
    elif session_plan.user_id != current_user.id:
        abort(404)

    session_plan_item = SessionPlanItem.query.filter_by(session_plan_id=session_plan_id, dso_id=dso_id).first()
    if session_plan_item:
        db.session.delete(session_plan_item)
        db.session.commit()
        result = 'off'
    else:
        session_plan_item = session_plan.create_new_deepsky_object_item(dso_id)
        db.session.add(session_plan_item)
        db.session.commit()
        result = 'on'
    return jsonify(result=result)


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/seltab')
def deepskyobject_seltab(dso_id):
    """View a deepsky object seltab."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    seltab = request.args.get('seltab', None)

    if not seltab and request.args.get('embed'):
        seltab = session.get('dso_embed_seltab', None)

    if seltab:
        if seltab == 'chart':
            return _do_redirect('main_deepskyobject.deepskyobject_chart', dso)
        if seltab == 'surveys':
            return _do_redirect('main_deepskyobject.deepskyobject_surveys', dso)
        if seltab == 'observations':
            return _do_redirect('main_deepskyobject.deepskyobject_observations', dso)
        if seltab == 'catalogue_data':
            return _do_redirect('main_deepskyobject.deepskyobject_catalogue_data', dso)

    back = request.args.get('back')
    if back == 'running_plan':
        return _do_redirect('main_deepskyobject.deepskyobject_observation_log', dso)

    return _do_redirect('main_deepskyobject.deepskyobject_info', dso)


@main_deepskyobject.route('/deepskyobject/<string:dso_id>')
@main_deepskyobject.route('/deepskyobject/<string:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['dso_embed_seltab'] = 'info'

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=False)
    user_descr = None
    apert_descriptions = []
    title_img = None
    if editor_user:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code=lang).first()
        user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code=lang) \
            .filter(func.coalesce(UserDsoApertureDescription.text, '') != '') \
            .order_by(UserDsoApertureDescription.aperture_class, UserDsoApertureDescription.lang_code)
        for apdescr in user_apert_descrs:
            if apdescr.aperture_class not in [cl[0] for cl in apert_descriptions] and apdescr.text:
                if apdescr.aperture_class == '<100':
                    apert_descriptions.insert(0, (apdescr.aperture_class, apdescr.text))
                else:
                    apert_descriptions.append((apdescr.aperture_class, apdescr.text))

        if user_descr and (not user_descr.text or not user_descr.text.startswith('![<]($IMG_DIR/')):
            image_info = get_dso_image_info_with_imgdir(dso.normalized_name_for_img())
            if image_info is not None:
                title_img = image_info[0]

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='info')

    editable = current_user.is_editor()
    descr_available = user_descr and user_descr.text or any([adescr for adescr in apert_descriptions])
    dso_image_info = get_dso_image_info(dso.normalized_name_for_img())

    other_names = _get_other_names(dso)

    wish_list = None
    observed_list = None
    offered_session_plans = None
    if current_user.is_authenticated:
        wish_item = WishListItem.query.filter(WishListItem.dso_id.in_((dso.id, orig_dso.id))) \
            .join(WishList) \
            .filter(WishList.user_id == current_user.id) \
            .first()
        wish_list = [wish_item.dso_id] if wish_item else []

        observed_item = ObservedListItem.query.filter(ObservedListItem.dso_id.in_((dso.id, orig_dso.id))) \
            .join(ObservedList) \
            .filter(ObservedList.user_id == current_user.id) \
            .first()
        observed_list = [observed_item.dso_id] if observed_item is not None else []

        if embed != 'pl':
            offered_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False) \
                .order_by(SessionPlan.for_date.desc()).all()
    else:
        if embed != 'pl':
            session_plan_id = session.get('session_plan_id')
            if session_plan_id:
                offered_session_plans = SessionPlan.query.filter_by(id=session_plan_id) \
                    .order_by(SessionPlan.for_date.desc()).all()

    has_observations = _has_dso_observations(dso, orig_dso)

    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr, apert_descriptions=apert_descriptions,
                           editable=editable, descr_available=descr_available, dso_image_info=dso_image_info, other_names=other_names,
                           wish_list=wish_list, observed_list=observed_list, offered_session_plans=offered_session_plans,
                           title_img=title_img, embed=embed, has_observations=has_observations,
                           prev_wrap=prev_wrap, next_wrap=next_wrap,
                           )


def _get_observations_query(dso, orig_dso):
    query = Observation.query \
        .join(ObservingSession) \
        .join(dso_observation_association_table) \
        .join(DeepskyObject) \
        .filter((ObservingSession.user_id == current_user.id) & DeepskyObject.id.in_((dso.id, orig_dso.id)))
    return query


def _has_dso_observations(dso, orig_dso):
    has_observations = False
    if current_user.is_authenticated:
        back = request.args.get('back')
        has_observations = (back != 'running_plan') and \
            db.session.query(literal(True)).filter(_get_observations_query(dso, orig_dso).exists()).scalar()
    return has_observations


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/surveys', methods=['GET', 'POST'])
def deepskyobject_surveys(dso_id):
    """Digital surveys view a deepsky object."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='surveys')
    exact_ang_size = (3.0*dso.major_axis/60.0/60.0) if dso.major_axis else 1.0

    field_size = _get_survey_field_size(ALADIN_ANG_SIZES, exact_ang_size, 10.0)
    embed = request.args.get('embed', None)

    if embed:
        session['dso_embed_seltab'] = 'surveys'

    has_observations = _has_dso_observations(dso, orig_dso)

    return render_template('main/catalogue/deepskyobject_info.html', type='surveys', dso=dso,
                           field_size=field_size, embed=embed, has_observations=has_observations,
                           prev_wrap=prev_wrap, next_wrap=next_wrap,
                           )


def _get_survey_field_size(ang_sizes, exact_ang_size, default_size):
    for i in range(len(ang_sizes)):
        if exact_ang_size < ang_sizes[i]:
            return ang_sizes[i]
    return default_size


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/observations')
def deepskyobject_observations(dso_id):
    """View a deepsky object observations."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='observations')

    other_names = _get_other_names(dso)
    embed = request.args.get('embed', None)

    if embed:
        session['dso_embed_seltab'] = 'observations'

    observations = None
    if current_user.is_authenticated:
        observations = _get_observations_query(dso, orig_dso).all()

    if not observations:
        return _do_redirect('main_deepskyobject.deepskyobject_info', dso)

    return render_template('main/catalogue/deepskyobject_info.html', type='observations', dso=dso,
                           prev_wrap=prev_wrap, next_wrap=next_wrap, other_names=other_names,
                           embed=embed, has_observations=True, observations=observations,
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object catalog data."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='catalogue_data')

    other_names = _get_other_names(dso)
    embed = request.args.get('embed', None)

    if embed:
        session['dso_embed_seltab'] = 'catalogue_data'

    has_observations = _has_dso_observations(dso, orig_dso)

    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           prev_wrap=prev_wrap, next_wrap=next_wrap, other_names=other_names,
                           embed=embed, has_observations=has_observations,
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/chart', methods=['GET', 'POST'])
def deepskyobject_chart(dso_id):
    """View a deepsky object chart."""
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    form = ChartForm()

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='chart')

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = dso.ra
            form.dec.data = dso.dec

    chart_control = common_prepare_chart_data(form, cancel_selection_url=url_for('main_deepskyobject.deepskyobject_chart', dso_id=dso.name))

    back = request.args.get('back')
    back_id = request.args.get('back_id')

    season = request.args.get('season')
    embed = request.args.get('embed')

    if embed:
        session['dso_embed_seltab'] = 'chart'

    back = request.args.get('back')
    if back == 'running_plan':
        iframe_endpoit = 'main_deepskyobject.deepskyobject_observation_log'
    else:
        iframe_endpoit = 'main_deepskyobject.deepskyobject_info'

    default_chart_iframe_url = url_for(iframe_endpoit, back=back, back_id=back_id, dso_id=dso.name, season=season, embed='fc', allow_back='true')

    has_observations = _has_dso_observations(dso, orig_dso)

    return render_template('main/catalogue/deepskyobject_info.html', fchart_form=form, type='chart', dso=dso,
                           chart_control=chart_control, default_chart_iframe_url=default_chart_iframe_url,
                           embed=embed, has_observations=has_observations,
                           prev_wrap=prev_wrap, next_wrap=next_wrap,
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def deepskyobject_chart_pos_img(dso_id, ra, dec):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None

    highlights_dso_list = None
    highlights_pos_list = None

    highlights_dso_list, highlights_pos_list = create_hightlights_lists()

    img_bytes = common_chart_pos_img(dso.ra, dso.dec, ra, dec, dso_names=(dso.name,), visible_objects=visible_objects,
                                     highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def deepskyobject_chart_legend_img(dso_id, ra, dec):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    img_bytes = common_chart_legend_img(dso.ra, dso.dec, ra, dec, )

    return send_file(img_bytes, mimetype='image/png')


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def chart_pdf(dso_id, ra, dec):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)

    img_bytes = common_chart_pdf_img(dso.ra, dso.dec, ra, dec, dso_names=[dso.name])

    return send_file(img_bytes, mimetype='application/pdf')


@main_deepskyobject.route('/deepskyobject/<int:dso_id>/edit', methods=['GET', 'POST'])
@login_required
def deepskyobject_edit(dso_id):
    """Update deepsky object."""
    if not current_user.is_editor():
        abort(403)
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=False)
    user_descr = None
    form = DeepskyObjectEditForm()
    if editor_user:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code=lang).first()
        authors = {}

        is_new = False
        if not user_descr:
            user_descr = UserDsoDescription(
                dso_id=dso_id,
                user_id=editor_user.id,
                rating=form.rating.data,
                lang_code=lang,
                common_name='',
                text='',
                references='',
                cons_order=1,
                create_by=current_user.id,
                create_date=datetime.now(),
                )
            is_new = True

        all_user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id, user_id=editor_user.id, lang_code=lang) \
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
                    dso_id=dso_id,
                    user_id=editor_user.id,
                    rating=1,
                    lang_code=lang,
                    aperture_class=aperture_class,
                    text='',
                    create_by=current_user.id,
                    create_date=datetime.now(),
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
            has_descr = False
            for adi in form.aperture_descr_items:
                for ad in user_apert_descriptions:
                    if ad.aperture_class == adi.aperture_class.data:
                        if adi.text.data:
                            ad.text = adi.text.data
                            ad.is_public = adi.is_public.data
                            ad.update_by = current_user.id
                            ad.update_date = datetime.now()
                            db.session.add(ad)
                            has_descr = True
                        elif ad.id is not None:
                            db.session.delete(ad)
            if is_new or was_text_changed or user_descr.common_name != form.common_name.data or \
                    user_descr.references != form.references.data or user_descr.rating != form.rating.data:
                user_descr.common_name = form.common_name.data
                user_descr.references = form.references.data
                user_descr.text = form.text.data
                user_descr.rating = form.rating.data
                if was_text_changed:
                    user_descr.update_by = current_user.id
                    user_descr.update_date = datetime.now()
                if has_descr or user_descr.text:
                    db.session.add(user_descr)
                else:
                    db.session.delete(user_descr)
            db.session.commit()

            flash('Deepsky object successfully updated', 'form-success')

            if form.goback.data != 'true':
                return redirect(url_for('main_deepskyobject.deepskyobject_edit', dso_id=dso_id))

            back = request.args.get('back')
            back_id = request.args.get('back_id')
            if back == 'constell':
                return redirect(url_for('main_constellation.constellation_info', constellation_id=back_id, _anchor='dso' + str(dso.id)))
            return redirect(url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back=back, back_id=back_id))

    authors['dso'] = _create_author_entry(user_descr.update_by, user_descr.update_date)
    for ad in user_apert_descriptions:
        authors[ad.aperture_class] = _create_author_entry(ad.update_by, ad.update_date)

    return render_template('main/catalogue/deepskyobject_edit.html', form=form, dso=dso, authors=authors, is_new=False)


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/observation-log', methods=['GET', 'POST'])
def deepskyobject_observation_log(dso_id):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    back = request.args.get('back')
    if back != 'running_plan':
        abort(404)

    back_id = request.args.get('back_id')
    observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
    if observation_plan_run is None or observation_plan_run.session_plan.user_id != current_user.id:
        abort(404)

    form = DeepskyObjectObservationLogForm()

    observation = observation_plan_run.observing_session.find_observation_by_dso_id(dso.id)

    is_new_observation_log = observation is None

    if is_new_observation_log:
        now = datetime.now()
        observation = Observation(
            observing_session_id=observation_plan_run.observing_session.id,
            target_type=ObservationTargetType.DSO,
            date_from=now,
            date_to=now,
            notes=form.notes.data if form.notes.data else '',
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        observation.deepsky_objects.append(dso)

    if request.method == 'POST':
        if form.validate_on_submit():
            observation.notes = form.notes.data
            observation.update_by = current_user.id
            observation.update_date = datetime.now()
            db.session.add(observation)
            db.session.commit()
            flash('Observation log successfully updated', 'form-success')
            return redirect(url_for('main_deepskyobject.deepskyobject_observation_log', dso_id=dso_id, back=back, back_id=back_id, embed=request.args.get('embed')))
    else:
        form.notes.data = observation.notes

    embed = request.args.get('embed')
    if embed:
        session['dso_embed_seltab'] = 'obs_log'

    prev_wrap, next_wrap = create_prev_next_wrappers(orig_dso, tab='observation_log')

    return render_template('main/catalogue/deepskyobject_info.html', type='observation_log', dso=dso, form=form,
                           embed=embed, is_new_observation_log=is_new_observation_log, back=back, back_id=back_id,
                           has_observations=False,
                           prev_wrap=prev_wrap, next_wrap=next_wrap,
                           )


@main_deepskyobject.route('/deepskyobject/<string:dso_id>/observation-log-delete', methods=['GET', 'POST'])
def deepskyobject_observation_log_delete(dso_id):
    dso, orig_dso = _find_dso(dso_id)
    if dso is None:
        abort(404)
    back = request.args.get('back')
    if back != 'running_plan':
        abort(404)
    back_id = request.args.get('back_id')
    observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
    if observation_plan_run is None or observation_plan_run.session_plan.user_id != current_user.id:
        abort(404)

    observation = observation_plan_run.observing_session.find_observation_by_dso_id(dso.id)

    if observation is not None:
        db.session.delete(observation)
        db.session.commit()

    flash('Observation log deleted.', 'form-success')
    return redirect(url_for('main_deepskyobject.deepskyobject_observation_log', dso_id=dso_id, back=back, back_id=back_id))


def _create_author_entry(update_by, update_date):
    if update_by is None:
        return '', ''
    user_name = User.query.filter_by(id=update_by).first().user_name
    return user_name, update_date.strftime("%Y-%m-%d %H:%M")


def _filter_apert_descriptions(all_user_apert_descrs):
    apert_descriptions = []
    for apdescr in all_user_apert_descrs:
        if not apdescr.aperture_class in [cl[0] for cl in apert_descriptions]:
            apert_descriptions.append((apdescr.aperture_class, apdescr.text),)
    return apert_descriptions


def _do_redirect(url, dso):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = request.args.get('fullscreen')
    splitview = request.args.get('splitview')
    season = request.args.get('season')
    return redirect(url_for(url, dso_id=dso.name, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed, season=season))

