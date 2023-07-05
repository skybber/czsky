import numpy as np
import os
import json
import base64

from datetime import date, datetime, timedelta
import datetime as dt_module

from flask import (
    abort,
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import create_app

from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search, get_items_per_page, create_table_sort, \
    get_order_by_field
from app import scheduler

from .comet_forms import (
    SearchCometForm,
    SearchCobsForm,
    CometFindChartForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_prepare_date_from_to,
    common_chart_pdf_img,
    get_trajectory_b64,
    common_ra_dec_fsz_from_request,
)

from app.commons.comet_utils import update_comets_cobs_observations, update_evaluated_comet_brightness, \
    update_comets_positions, get_mag_coma_from_observations, get_all_comets, find_mpc_comet
from app.commons.utils import to_float

from app.models import (
    Comet,
    CometObservation,
    DB_UPDATE_COMETS,
)

from app.commons.dbupdate_utils import ask_dbupdate_permit

main_comet = Blueprint('main_comet', __name__)

comet_update_counter = 0

utc = dt_module.timezone.utc


def _update_comets():
    global comet_update_counter
    comet_update_counter += 1
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_COMETS, timedelta(hours=1)):
            update_comets_positions()
            if (comet_update_counter % 4) == 1:
                update_comets_cobs_observations()
            if (comet_update_counter % 2) == 1:
                update_evaluated_comet_brightness()


job1 = scheduler.add_job(_update_comets, 'cron', hour='1,4,7,10,13,16,19,22', replace_existing=True)


@main_comet.route('/comets', methods=['GET', 'POST'])
def comets():
    """View comets."""
    search_form = SearchCometForm()

    sort_def = { 'designation': Comet.designation,
                 'cur_ra': Comet.cur_ra,
                 'cur_dec': Comet.cur_dec,
                 'constellation': Comet.cur_constell_id,
                 'mag': Comet.mag,
                 'coma_diameter': Comet.real_coma_diameter,
                 }

    ret, page, sort_by = process_paginated_session_search('comet_search_page', 'comet_list_sort_by', [
        ('comet_search', search_form.q),
        ('comet_list_maglim', search_form.maglim),
        ('dec_min', search_form.dec_min),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_comet.comets'))

    table_sort = create_table_sort(sort_by, sort_def.keys())

    offset = (page - 1) * per_page

    comet_query = Comet.query.filter(Comet.mag < 20)

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"', '')
        comet_query = comet_query.filter(Comet.designation.like('%' + search_expr + '%'))
    else:
        if search_form.dec_min.data:
            comet_query = comet_query.filter(Comet.cur_dec > (np.pi * search_form.dec_min.data / 180.0))
        if search_form.maglim.data:
            comet_query = comet_query.filter(Comet.mag <= search_form.maglim.data)

    order_by_field = get_order_by_field(sort_def, sort_by)

    if order_by_field is None:
        order_by_field = Comet.mag

    shown_comets = comet_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=comet_query.count(), search=False,
                            record_name='comets', css_framework='semantic', not_passed_args='back')

    return render_template('main/solarsystem/comets.html', comets=shown_comets, pagination=pagination, search_form=search_form,
                           table_sort=table_sort)


@main_comet.route('/comet/<string:comet_id>', methods=['GET', 'POST'])
@main_comet.route('/comet/<string:comet_id>/info', methods=['GET', 'POST'])
def comet_info(comet_id):
    """View a comet info."""
    comet = find_mpc_comet(comet_id)
    if comet is None:
        abort(404)

    form = CometFindChartForm()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    body = sun + mpc.comet_orbit(comet, ts, GM_SUN)

    common_prepare_date_from_to(form)

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    t = ts.now()
    trajectory_b64 = None
    if (form.date_from.data is not None) and (form.date_to.data is not None) and form.date_from.data < form.date_to.data:
        d1 = datetime(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = datetime(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        today = date.today()
        if today < d1.date():
            t = ts.from_datetime(d1.replace(tzinfo=utc))
        elif today > d2.date():
            t = ts.from_datetime(d2.replace(tzinfo=utc))

        trajectory_b64 = get_trajectory_b64(d1, d2, ts, earth, body)

    comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(body).radec()
    comet_ra = comet_ra_ang.radians
    comet_dec = comet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            form.ra.data = comet_ra
            form.dec.data = comet_dec

    chart_control = common_prepare_chart_data(form)

    embed = request.args.get('embed')

    return render_template('main/solarsystem/comet_info.html', fchart_form=form, type='info', comet=comet, comet_ra=comet_ra, comet_dec=comet_dec,
                           chart_control=chart_control, trajectory=trajectory_b64, embed=embed)


@main_comet.route('/comet/<string:comet_id>/cobs-observations', methods=['GET', 'POST'])
def comet_cobs_observations(comet_id):
    """View a comet observations from cobs."""
    comet = Comet.query.filter_by(comet_id=comet_id).first()
    if comet is None:
        abort(404)

    search_form = SearchCobsForm()

    ret, page, _ = process_paginated_session_search('cobs_observs_page', None, [
        ('items_per_page', search_form.items_per_page)
    ])

    if not ret:
        return redirect(url_for('main_comet.comet_cobs_observations', comet_id=comet_id))

    cobs_observations = CometObservation.query.filter_by(comet_id=comet.id) \
        .order_by(CometObservation.date.desc()).all()

    per_page = get_items_per_page(search_form.items_per_page)

    page_offset = (page - 1) * per_page

    if page_offset < len(cobs_observations):
        page_items = cobs_observations[page_offset:page_offset + per_page]
    else:
        page_items = []

    pagination = Pagination(page=page, per_page=per_page, total=len(cobs_observations), search=False, record_name='cobs_observs',
                            css_framework='semantic', not_passed_args='back',)

    last_mag, last_coma_diameter = None, None
    if len(cobs_observations) > 0:
        last_mag, last_coma_diameter = get_mag_coma_from_observations(cobs_observations)

    if last_mag is not None:
        last_mag = '{:.2f}'.format(last_mag)
    else:
        last_mag = '-'

    if last_coma_diameter is not None:
        last_coma_diameter = '{:.2f}'.format(last_coma_diameter)
    else:
        last_coma_diameter = '-'

    embed = request.args.get('embed')

    return render_template('main/solarsystem/comet_info.html', type='cobs_observations', comet=comet, last_mag=last_mag,
                           last_coma_diameter=last_coma_diameter, cobs_observations=enumerate(page_items),
                           page_offset=page_offset, pagination=pagination, search_form=search_form, embed=embed)


@main_comet.route('/comet/<string:comet_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def comet_chart_pos_img(comet_id, ra, dec):
    comet = find_mpc_comet(comet_id)
    if comet is None:
        abort(404)

    comet_ra = to_float(request.args.get('obj_ra'), None)
    comet_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes, img_format = common_chart_pos_img(comet_ra, comet_dec, ra, dec, visible_objects=visible_objects, trajectory=trajectory)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_comet.route('/comet/<string:comet_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def comet_chart_legend_img(comet_id, ra, dec):
    comet = find_mpc_comet(comet_id)
    if comet is None:
        abort(404)

    comet_ra = to_float(request.args.get('obj_ra'), None)
    comet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(comet_ra, comet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_comet.route('/comet/<string:comet_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def comet_chart_pdf(comet_id, ra, dec):
    comet = find_mpc_comet(comet_id)
    if comet is None:
        abort(404)

    comet_ra = to_float(request.args.get('obj_ra'), None)
    comet_dec = to_float(request.args.get('obj_dec'), None)

    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pdf_img(comet_ra, comet_dec, ra, dec, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_comet.route('/comet/<string:comet_id>')
@main_comet.route('/comet/<string:comet_id>/catalogue_data')
def comet_catalogue_data(comet_id):
    """View a comet catalog info."""
    comet = find_mpc_comet(comet_id)
    if comet is None:
        abort(404)
    return render_template('main/solarsystem/comet_info.html', type='catalogue_data', user_descr=user_descr)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
