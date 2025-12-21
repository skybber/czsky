import os
from datetime import datetime, timedelta
import numpy as np
import base64

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
from app import scheduler
from app import create_app

from app.models import (
    Supernova,
    Observation,
    ObservingSession,
    ObservationTargetType,
    ObservedList,
    ObservedListItem,
    ObsSessionPlanRun,
    SessionPlan,
    SessionPlanItem,
    UserStarDescription,
    WishList,
    WishListItem,
    DB_UPDATE_SUPERNOVAE,
    DB_DELETE_SUPERNOVAE,
)

from app.commons.pagination import Pagination
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
)

from app.commons.search_utils import (
    process_paginated_session_search,
    get_items_per_page,
    create_table_sort,
    get_packed_constell_list,
    get_order_by_field,
)

from app.commons.supernova_loader import update_supernovae_from_rochesterastronomy
from app.commons.dso_utils import normalize_supernova_name

from app.main.chart.chart_forms import ChartForm
from app.commons.prevnext_utils import create_navigation_wrappers
from app.commons.highlights_list_utils import create_hightlights_lists

from .supernova_forms import SearchSupernovaForm
from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.commons.utils import is_splitview_supported

main_supernova = Blueprint('main_supernova', __name__)


def _update_supernovae():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_SUPERNOVAE, timedelta(days=1)):
            update_supernovae_from_rochesterastronomy()

def _delete_obsolete_supernovae():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_DELETE_SUPERNOVAE, timedelta(days=1)):
            threshold_date = datetime.utcnow() - timedelta(days=50)
            supernovas_to_delete = Supernova.query.filter(Supernova.latest_observed < threshold_date).all()
            for supernova in supernovas_to_delete:
                db.session.delete(supernova)
            db.session.commit()


job1 = scheduler.add_job(_update_supernovae, 'cron', hour='6,18', replace_existing=True)

job2 = scheduler.add_job(_delete_obsolete_supernovae, 'cron', hour='14', replace_existing=True, jitter=60)

@main_supernova.route('/supernovae', methods=['GET', 'POST'])
def supernovae():
    """View supernovae."""
    search_form = SearchSupernovaForm()

    ret, page, sort_by = process_paginated_session_search('sn_search_page', 'sn_sort_by', [
        ('sn_search', search_form.q),
        ('sn_constellation_id', search_form.constellation_id),
        ('sn_latest_mag_max', search_form.latest_mag_max),
        ('dec_min', search_form.dec_min),
        ('items_per_page', search_form.items_per_page)
    ])

    if not ret:
        return redirect(url_for('main_supernova.supernovae', page=page, sortby=sort_by))

    per_page = get_items_per_page(search_form.items_per_page)

    offset = (page - 1) * per_page

    supernova_query = Supernova.query
    if search_form.q.data:
        supernova_q = normalize_supernova_name(search_form.q.data)
        supernova_query = supernova_query.filter(Supernova.designation.like('%;' + supernova_q.strip() + ';%'))
    else:
        if search_form.constellation_id.data is not None:
            supernova_query = supernova_query.filter(Supernova.constellation_id == search_form.constellation_id.data)
        if search_form.latest_mag_max.data is not None:
            supernova_query = supernova_query.filter(Supernova.latest_mag < search_form.latest_mag_max.data)
        if search_form.dec_min.data is not None:
            supernova_query = supernova_query.filter(Supernova.dec > (np.pi * search_form.dec_min.data / 180.0))

    sort_def = {'designation': Supernova.designation,
                'host_galaxy': Supernova.host_galaxy,
                'constellation': Supernova.constellation_id,
                'ra': Supernova.ra,
                'dec': Supernova.dec,
                'offset': Supernova.offset,
                'latest_mag': Supernova.latest_mag,
                'latest_observed': Supernova.latest_observed,
                'sn_type': Supernova.sn_type,
                'z': Supernova.z,
                'max_mag': Supernova.max_mag,
                'max_mag_date': Supernova.max_mag_date,
                'first_observed': Supernova.first_observed,
                'discoverer': Supernova.discoverer,
                'aka': Supernova.aka,
                }

    table_sort = create_table_sort(sort_by, sort_def.keys())

    order_by_field = get_order_by_field(sort_def, sort_by)

    if order_by_field is None:
        order_by_field = Supernova.latest_mag

    shown_supernovae = supernova_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=supernova_query.count(), search=False, record_name='supernovae',
                            css_framework='semantic', not_passed_args='back')

    packed_constell_list = get_packed_constell_list()

    return render_template('main/catalogue/supernovae.html', supernovae=shown_supernovae, pagination=pagination,
                           search_form=search_form, table_sort=table_sort, packed_constell_list=packed_constell_list)


@main_supernova.route('/supernova/<string:designation>/info')
def supernova_info(designation):
    """View a supernova catalogue data."""
    supernova = Supernova.query.filter_by(designation=designation).first()
    if supernova is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['supernova_embed_seltab'] = 'catalogue_data'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(supernova)

    return render_template('main/catalogue/supernova_info.html', type='info', supernova=supernova, embed=embed,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,)


@main_supernova.route('/supernova/<string:designation>/surveys')
def supernova_surveys(designation):
    """View a supernova catalogue data."""
    supernova = Supernova.query.filter_by(designation=designation).first()
    if supernova is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['supernova_embed_seltab'] = 'surveys'

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(supernova)

    return render_template('main/catalogue/supernova_info.html', type='surveys', supernova=supernova,
                           embed=embed, prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap, field_size=40.0)


@main_supernova.route('/supernova/<string:designation>/seltab')
def supernova_seltab(designation):
    """View a supernova seltab."""
    supernova = Supernova.query.filter_by(designation=designation).first()
    if not supernova:
        abort(404)

    seltab = request.args.get('seltab', None)

    if not seltab and request.args.get('embed'):
        seltab = session.get('supernova_embed_seltab', None)

    if seltab:
        if seltab == 'chart':
            return _do_redirect('main_supernova.supernova_chart', supernova)
        if seltab == 'surveys':
            return _do_redirect('main_supernova.supernova_surveys', supernova)

    if is_splitview_supported():
        return _do_redirect('main_supernova.supernova_chart', supernova, splitview=True)

    return _do_redirect('main_supernova.supernova_info', supernova)


@main_supernova.route('/supernova/<string:designation>/chart', methods=['GET', 'POST'])
@csrf.exempt
def supernova_chart(designation):
    """View a supernova findchart."""
    supernova = Supernova.query.filter_by(designation=designation).first()
    if not supernova:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['supernova_embed_seltab'] = 'info'

    form = ChartForm()

    common_ra_dec_dt_fsz_from_request(form, supernova.ra, supernova.dec, 60)

    chart_control = common_prepare_chart_data(form)

    prev_wrap, cur_wrap, next_wrap = create_navigation_wrappers(supernova)

    back = request.args.get('back')
    back_id = request.args.get('back_id')

    default_chart_iframe_url = url_for('main_supernova.supernova_info', designation=designation, back=back, back_id=back_id, embed='fc', allow_back='true')

    return render_template('main/catalogue/supernova_info.html', fchart_form=form, type='chart', supernova=supernova, chart_control=chart_control,
                           prev_wrap=prev_wrap, cur_wrap=cur_wrap, next_wrap=next_wrap,
                           default_chart_iframe_url=default_chart_iframe_url, embed=embed,)


@main_supernova.route('/supernova/<string:designation>/chart-pos-img', methods=['GET'])
def supernova_chart_pos_img(designation):
    supernova = Supernova.query.filter_by(designation=designation).first()
    if supernova is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None

    highlights_dso_list, highlights_pos_list = create_hightlights_lists()

    img_bytes, img_format = common_chart_pos_img(supernova.ra, supernova.dec, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list, )

    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_supernova.route('/supernova/<string:designation>/chart-pdf', methods=['GET'])
def supernova_chart_pdf(designation):
    supernova = Supernova.query.filter_by(designation=designation).first()
    if supernova is None:
        abort(404)

    img_bytes = common_chart_pdf_img(supernova.ra, supernova.dec)

    return send_file(img_bytes, mimetype='application/pdf')


def _do_redirect(url, supernova, splitview=False):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = request.args.get('fullscreen')
    splitview = 'true' if splitview else request.args.get('splitview')
    season = request.args.get('season')
    dt = request.args.get('dt')
    return redirect(url_for(url, designation=supernova.designation, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed, season=season, dt=dt))
