from datetime import datetime
import numpy as np
import base64

from sqlalchemy import or_

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.sql.expression import literal

from app import db, csrf

from app.models import (
    DoubleStar,
    Observation,
    ObservingSession,
    ObservationTargetType,
    ObservedList,
    ObservedListItem,
    SessionPlan,
    SessionPlanItem,
    UserDoubleStarDescription,
    WishList,
    WishListItem,
)

from app.commons.pagination import Pagination
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
)

from app.commons.utils import get_lang_and_editor_user_from_request, is_splitview_supported, \
    get_lang_and_all_editor_users_from_request
from app.commons.search_utils import (
    process_paginated_session_search,
    get_items_per_page,
    create_table_sort,
    get_packed_constell_list,
    get_order_by_field,
)

from app.commons.dso_utils import normalize_double_star_name

from app.main.chart.chart_forms import ChartForm
from app.commons.prevnext_utils import create_navigation_wrappers
from app.commons.highlights_list_utils import create_hightlights_lists
from app.commons.observing_session_utils import find_observing_session, show_observation_log, combine_observing_session_date_time
from app.commons.observation_form_utils import assign_equipment_choices

from .double_star_forms import SearchDoubleStarForm, DoubleStarEditForm

from app.main.forms import ObservationLogNoFilterForm

main_double_star = Blueprint('main_double_star', __name__)


@main_double_star.route('/double-stars', methods=['GET', 'POST'])
def double_stars():
    """View double stars."""
    search_form = SearchDoubleStarForm()

    ret, page, sort_by = process_paginated_session_search('dbl_star_search_page', 'dbl_sort_by', [
        ('dbl_star_search', search_form.q),
        ('constellation_id', search_form.constellation_id),
        ('dbl_mag_max', search_form.mag_max),
        ('dbl_delta_mag_min', search_form.delta_mag_min),
        ('dbl_delta_mag_max', search_form.delta_mag_max),
        ('dbl_separation_min', search_form.separation_min),
        ('dbl_separation_max', search_form.separation_max),
        ('dec_min', search_form.dec_min),
        ('items_per_page', search_form.items_per_page)
    ])

    if not ret:
        return redirect(url_for('main_double_star.double_stars', page=page, sortby=sort_by))

    per_page = get_items_per_page(search_form.items_per_page)

    offset = (page - 1) * per_page

    dbl_star_query = DoubleStar.query
    if search_form.q.data:
        double_star_q = normalize_double_star_name(search_form.q.data)
        dbl_star_query = dbl_star_query.filter(or_(DoubleStar.common_cat_id == double_star_q,
                                               DoubleStar.wds_number == search_form.q.data.strip(),
                                               DoubleStar.norm_other_designation.like('%;' + search_form.q.data.strip() + ';%')
                                               ))
    else:
        if search_form.constellation_id.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.constellation_id == search_form.constellation_id.data)
        if search_form.mag_max.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.mag_first < search_form.mag_max.data, DoubleStar.mag_second < search_form.mag_max.data)
        if search_form.delta_mag_min.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.delta_mag > search_form.delta_mag_min.data)
        if search_form.delta_mag_max.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.delta_mag < search_form.delta_mag_max.data)
        if search_form.separation_min.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.separation > search_form.separation_min.data)
        if search_form.separation_max.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.separation < search_form.separation_max.data)
        if search_form.dec_min.data is not None:
            dbl_star_query = dbl_star_query.filter(DoubleStar.dec_first > (np.pi * search_form.dec_min.data / 180.0))

    sort_def = { 'wds_number': DoubleStar.wds_number,
                 'common_cat_id': DoubleStar.common_cat_id,
                 'components': DoubleStar.components,
                 'other_designation': DoubleStar.other_designation,
                 'ra': DoubleStar.ra_first,
                 'dec': DoubleStar.dec_first,
                 'mag_first': DoubleStar.mag_first,
                 'mag_second': DoubleStar.mag_second,
                 'separation': DoubleStar.separation,
                 'spectral_type': DoubleStar.spectral_type,
                 'constellation': DoubleStar.constellation_id,
                 }

    table_sort = create_table_sort(sort_by, sort_def.keys())

    order_by_field = get_order_by_field(sort_def, sort_by)

    if order_by_field is None:
        order_by_field = DoubleStar.id

    shown_double_stars = dbl_star_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=dbl_star_query.count(), search=False, record_name='double_stars',
                            css_framework='semantic', not_passed_args='back')

    packed_constell_list = get_packed_constell_list()

    return render_template('main/catalogue/double_stars.html', double_stars=shown_double_stars, pagination=pagination,
                           search_form=search_form, table_sort=table_sort, packed_constell_list=packed_constell_list)


@main_double_star.route('/double-star/<int:double_star_id>/info')
def double_star_info(double_star_id):
    """View a double star catalogue data."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'info'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star)

    user_descr = _get_user_descr(double_star_id)

    wish_list = None
    observed_list = None
    offered_session_plans = None
    if current_user.is_authenticated:
        wish_item = WishListItem.query.filter_by(double_star_id=double_star.id).first()
        wish_list = [wish_item.double_star_id] if wish_item else []

        observed_item = ObservedListItem.query.filter_by(double_star_id=double_star.id).first()
        observed_list = [observed_item.double_star_id] if observed_item else []

        if embed != 'pl':
            offered_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False).all()
    else:
        if embed != 'pl':
            session_plan_id = session.get('session_plan_id')
            if session_plan_id:
                offered_session_plans = SessionPlan.query.filter_by(id=session_plan_id).all()

    has_observations = _has_double_star_observations(double_star)
    show_obs_log = show_observation_log()
    editable = current_user.is_editor()

    return render_template('main/catalogue/double_star_info.html', type='info', double_star=double_star,
                           wish_list=wish_list, observed_list=observed_list, offered_session_plans=offered_session_plans,
                           embed=embed, prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap, user_descr=user_descr,
                           has_observations=has_observations, show_obs_log=show_obs_log, editable=editable)


def _get_observations_query(double_star):
    query = Observation.query.join(ObservingSession) \
        .filter((ObservingSession.user_id == current_user.id) & (Observation.double_star_id == double_star.id))
    return query


def _has_double_star_observations(double_star):
    has_observations = False
    if current_user.is_authenticated:
        back = request.args.get('back')
        has_observations = (back != 'running_plan') and \
                           db.session.query(literal(True)).filter(_get_observations_query(double_star).exists()).scalar()
    return has_observations


@main_double_star.route('/double-star/<int:double_star_id>/surveys')
def double_star_surveys(double_star_id):
    """View a double star catalogue data."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'surveys'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star)

    user_descr = _get_user_descr(double_star_id)
    has_observations = _has_double_star_observations(double_star)
    show_obs_log = show_observation_log()

    return render_template('main/catalogue/double_star_info.html', type='surveys', double_star=double_star, embed=embed,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           user_descr=user_descr, has_observations=has_observations, show_obs_log=show_obs_log, field_size=40.0)


@main_double_star.route('/double-star/<int:double_star_id>/observations')
def double_star_observations(double_star_id):
    """View a double star object observations."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star, tab='observations')

    embed = request.args.get('embed', None)

    if embed:
        session['double_star_embed_seltab'] = 'observations'

    observations = None
    if current_user.is_authenticated:
        observations = _get_observations_query().all()

    if not observations:
        return _do_redirect('main_double_star.double_star_info', double_star)

    show_obs_log = show_observation_log()
    return render_template('main/catalogue/double_star_info.html', type='observations', double_star=double_star,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           embed=embed, has_observations=True, show_obs_log=show_obs_log, observations=observations,
                           )


@main_double_star.route('/double-star/<int:double_star_id>/catalogue-data')
def double_star_catalogue_data(double_star_id):
    """View a double star catalogue data."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'catalogue_data'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star)

    user_descr = _get_user_descr(double_star_id)

    has_observations = _has_double_star_observations(double_star)
    show_obs_log = show_observation_log()

    return render_template('main/catalogue/double_star_info.html', type='catalogue_data', double_star=double_star, embed=embed,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           user_descr=user_descr, has_observations=has_observations, show_obs_log=show_obs_log, )


@main_double_star.route('/double-star/switch-wish-list', methods=['GET'])
@login_required
def double_star_switch_wish_list():
    double_star_id = request.args.get('double_star_id', None, type=int)
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    wish_list_item = WishListItem.query.filter_by(wish_list_id=wish_list.id, double_star_id=double_star_id).first()
    if wish_list_item:
        db.session.delete(wish_list_item)
        db.session.commit()
        result = 'off'
    else:
        wish_list_item = wish_list.create_new_double_star_item(double_star_id)
        db.session.add(wish_list_item)
        db.session.commit()
        result = 'on'
    return jsonify(result=result)


@main_double_star.route('/double-star/switch-observed-list', methods=['GET'])
@login_required
def double_star_switch_observed_list():
    double_star_id = request.args.get('double_star_id', None, type=int)
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    observed_list_item = ObservedListItem.query.filter_by(observed_list_id=observed_list.id, double_star_id=double_star_id).first()
    if observed_list_item:
        db.session.delete(observed_list_item)
        db.session.commit()
        result = 'off'
    else:
        observed_list_item = observed_list.create_new_double_star_item(double_star_id)
        db.session.add(observed_list_item)
        db.session.commit()
        result = 'on'
    return jsonify(result=result)


@main_double_star.route('/double-star/switch-session-plan', methods=['GET'])
def double_star_switch_session_plan():
    double_star_id = request.args.get('double_star_id', None, type=int)
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
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

    session_plan_item = SessionPlanItem.query.filter_by(session_plan_id=session_plan_id, double_star_id=double_star_id).first()
    if session_plan_item:
        db.session.delete(session_plan_item)
        db.session.commit()
        result = 'off'
    else:
        session_plan_item = session_plan.create_new_double_star_item(double_star_id)
        db.session.add(session_plan_item)
        db.session.commit()
        result = 'on'
    return jsonify(result=result)


@main_double_star.route('/double-star/<int:double_star_id>/seltab')
def double_star_seltab(double_star_id):
    """View a double star seltab."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if not double_star:
        abort(404)

    seltab = request.args.get('seltab', None)

    if not seltab and request.args.get('embed'):
        seltab = session.get('double_star_embed_seltab', None)

    if seltab:
        if seltab == 'chart':
            return _do_redirect('main_double_star.double_star_chart', double_star)
        if seltab == 'surveys':
            return _do_redirect('main_double_star.double_star_surveys', double_star)
        if seltab == 'observations':
            return _do_redirect('main_double_star.double_star_observations', double_star)

    if show_observation_log():
        return _do_redirect('main_double_star.double_star_observation_log', double_star)

    if is_splitview_supported():
        return _do_redirect('main_double_star.double_star_chart', double_star, splitview=True)

    if request.args.get('embed'):
        return _do_redirect('main_double_star.double_star_info', double_star)

    return _do_redirect('main_double_star.double_star_chart', double_star)


@main_double_star.route('/double-star/<int:double_star_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def double_star_chart(double_star_id):
    """View a double star findchart."""
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if not double_star:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['double_star_embed_seltab'] = 'catalogue_data'

    form = ChartForm()

    common_ra_dec_dt_fsz_from_request(form, double_star.ra_first, double_star.dec_first, 60)

    chart_control = common_prepare_chart_data(form)

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star)

    user_descr = _get_user_descr(double_star_id)
    has_observations = _has_double_star_observations(double_star)
    show_obs_log = show_observation_log()

    back = request.args.get('back')
    back_id = request.args.get('back_id')

    default_chart_iframe_url = url_for('main_double_star.double_star_info', back=back, back_id=back_id, double_star_id=double_star_id, embed='fc', allow_back='true')

    return render_template('main/catalogue/double_star_info.html', fchart_form=form, type='chart', double_star=double_star, chart_control=chart_control,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           default_chart_iframe_url=default_chart_iframe_url, embed=embed, user_descr=user_descr,
                           has_observations=has_observations, show_obs_log=show_obs_log,)


@main_double_star.route('/double-star/<string:double_star_id>/chart-pos-img', methods=['GET'])
def double_star_chart_pos_img(double_star_id):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None

    highlights_dso_list, highlights_pos_list = create_hightlights_lists()

    img_bytes, img_format = common_chart_pos_img(double_star.ra_first, double_star.dec_first, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list, )

    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_double_star.route('/double-star/<string:double_star_id>/chart-pdf', methods=['GET'])
def double_star_chart_pdf(double_star_id):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    img_bytes = common_chart_pdf_img(double_star.ra_first, double_star.dec_first)

    return send_file(img_bytes, mimetype='application/pdf')


@main_double_star.route('/double-star/<string:double_star_id>/observation-log', methods=['GET', 'POST'])
def double_star_observation_log(double_star_id):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    form = ObservationLogNoFilterForm()
    assign_equipment_choices(form, False)

    observation = observing_session.find_observation_by_double_star_id(double_star.id)

    is_new_observation_log = observation is None

    if is_new_observation_log:
        date_from = datetime.now()
        if date_from.date() != observing_session.date_from.date() and date_from.date() != observing_session.date_to.date():
            date_from = observing_session.date_from

        observation = Observation(
            observing_session_id=observing_session.id,
            double_star_id=double_star.id,
            target_type=ObservationTargetType.DBL_STAR,
            date_from=date_from,
            date_to=date_from,
            notes=form.notes.data if form.notes.data else '',
            telescope_id = form.telescope.data if form.telescope.data != -1 else None,
            eyepiece_id = form.eyepiece.data if form.eyepiece.data != -1 else None,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            observation.notes = form.notes.data
            form.telescope.data = observation.telescope_id if observation.telescope_id is not None else -1
            form.eyepiece.data = observation.eyepiece_id if observation.eyepiece_id is not None else -1
            observation.date_from = combine_observing_session_date_time(observing_session, form.date_from.data, form.time_from.data)
            observation.update_by = current_user.id
            observation.update_date = datetime.now()
            db.session.add(observation)
            db.session.commit()
            flash('Observation log successfully updated', 'form-success')
            return redirect(url_for('main_double_star.double_star_observation_log', double_star_id=double_star_id, back=back, back_id=back_id, embed=request.args.get('embed')))
    else:
        form.notes.data = observation.notes
        if observation.telescope_id:
            form.telescope.data = observation.telescope_id
        elif observing_session.default_telescope_id is not None:
            form.telescope.data = observing_session.default_telescope_id
        else:
            form.telescope.data = -1
        form.eyepiece.data = observation.eyepiece_id if observation.eyepiece_id is not None else -1
        form.date_from.data = observation.date_from
        form.time_from.data = observation.date_from

    embed = request.args.get('embed')
    if embed:
        session['dso_embed_seltab'] = 'obs_log'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(double_star, tab='observation_log')

    return render_template('main/catalogue/double_star_info.html', type='observation_log', double_star=double_star, form=form,
                           embed=embed, is_new_observation_log=is_new_observation_log, observing_session=observing_session,
                           back=back, back_id=back_id, has_observations=False, show_obs_log=True,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           )


@main_double_star.route('/double-star/<string:double_star_id>/observation-log-delete', methods=['GET', 'POST'])
def double_star_observation_log_delete(double_star_id):
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    observation = observing_session.find_observation_by_double_star_id(double_star.id)

    if observation is not None:
        db.session.delete(observation)
        db.session.commit()

    flash('Observation log deleted.', 'form-success')
    return redirect(url_for('main_double_star.double_star_observation_log', double_star_id=double_star_id, back=back, back_id=back_id))


@main_double_star.route('/double-star/<int:double_star_id>/edit', methods=['GET', 'POST'])
@login_required
def double_star_edit(double_star_id):
    """Update user double star description object."""
    if not current_user.is_editor():
        abort(403)
    double_star = DoubleStar.query.filter_by(id=double_star_id).first()
    if double_star is None:
        abort(404)

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=False)
    form = DoubleStarEditForm()
    if editor_user:
        user_descr = UserDoubleStarDescription.query.filter_by(double_star_id=double_star_id, user_id=editor_user.id).first()
        is_new = False
        if not user_descr:
            user_descr = UserDoubleStarDescription(
                double_star_id=double_star_id,
                user_id=editor_user.id,
                lang_code=lang,
                common_name='',
                text='',
                references='',
                cons_order=1,
                create_by=current_user.id,
                create_date=datetime.now(),
                )
            is_new = True

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
            flash('Double star description successfully updated', 'form-success')
            if form.goback.data != 'true':
                return redirect(url_for('main_double_star.double_star_edit', double_star_id=double_star_id))
            back = request.args.get('back')
            back_id = request.args.get('back_id')
            if back == 'constell':
                return redirect(url_for('main_constellation.constellation_info', constellation_id=back_id, _anchor='doublestar' + str(double_star_id)))
            return redirect(url_for('main_double_star.double_star_info', double_star_id=double_star_id))

    return render_template('main/catalogue/double_star_edit.html', form=form, double_star=double_star, user_descr=user_descr, is_new=is_new)


def _do_redirect(url, double_star, splitview=False):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = request.args.get('fullscreen')
    splitview = 'true' if splitview else request.args.get('splitview')
    season = request.args.get('season')
    dt = request.args.get('dt')
    return redirect(url_for(url, double_star_id=double_star.id, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed, season=season, dt=dt))


def _get_user_descr(double_star_id):
    lang, all_editor_users = get_lang_and_all_editor_users_from_request(for_constell_descr=False)
    if all_editor_users:
        for editor_user in all_editor_users:
            udsd = UserDoubleStarDescription.query.filter_by(double_star_id=double_star_id, user_id=editor_user.id, lang_code=lang).first()
            if udsd:
                return udsd
    return None
