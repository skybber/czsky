import numpy as np
import os
import math
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
from app import scheduler

from app.models import (
    MinorPlanet,
    DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY, Constellation,
)

from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search, get_items_per_page, create_table_sort, \
    get_order_by_field

from .minor_planet_forms import (
    SearchMinorPlanetForm,
    MinorPlanetFindChartForm,
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

from app.commons.utils import to_float
from app.commons.minor_planet_utils import get_all_mpc_minor_planets, update_minor_planets_positions, update_minor_planets_brightness

from app.commons.dbupdate_utils import ask_dbupdate_permit

utc = dt_module.timezone.utc

main_minor_planet = Blueprint('main_minor_planet', __name__)


def _update_minor_planet_positions():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY, timedelta(hours=1)):
            update_minor_planets_positions()
            update_minor_planets_brightness()


job1 = scheduler.add_job(_update_minor_planet_positions, 'cron', hour=14, replace_existing=True, jitter=60)


def _get_apparent_magnitude_hg( H_absolute_magnitude, G_slope, body_earth_distanceAU, body_sun_distanceAU, earth_sun_distanceAU ):
    beta = math.acos(
                        (body_sun_distanceAU * body_sun_distanceAU + body_earth_distanceAU * body_earth_distanceAU - earth_sun_distanceAU * earth_sun_distanceAU) /
                        (2 * body_sun_distanceAU * body_earth_distanceAU)
                    )

    psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 0.63)
    Psi_1 = math.exp(-3.33 * psi_t)
    psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 1.22)
    Psi_2 = math.exp(-1.87 * psi_t)

    # Have found a combination of G_slope, Psi_1 and Psi_2 can lead to a negative value in the log calculation.
    try:
        apparentMagnitude = H_absolute_magnitude + \
                            5.0 * math.log10(body_sun_distanceAU * body_earth_distanceAU) - \
                            2.5 * math.log10((1 - G_slope) * Psi_1 + G_slope * Psi_2)
    except:
        apparentMagnitude = None

    return apparentMagnitude


@main_minor_planet.route('/minor-planets', methods=['GET', 'POST'])
def minor_planets():
    """View minor_planets."""
    search_form = SearchMinorPlanetForm()

    sort_def = { 'designation': MinorPlanet.designation,
                 'cur_ra': MinorPlanet.cur_ra,
                 'cur_dec': MinorPlanet.cur_dec,
                 'constellation': MinorPlanet.cur_constell_id,
                 'eval_mag': MinorPlanet.eval_mag,
                 }

    ret, page, sort_by = process_paginated_session_search('minor_planet_search_page', 'minor_planet_sort_by', [
        ('minor_planet_search', search_form.q),
        ('minor_planet_season', search_form.season),
        ('minor_planet_maglim', search_form.maglim),
        ('dec_min', search_form.dec_min),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_minor_planet.minor_planets'))

    table_sort = create_table_sort(sort_by, sort_def.keys())

    offset = (page - 1) * per_page
    minor_planet_query = MinorPlanet.query

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"', '')
        minor_planet_query = minor_planet_query.filter(MinorPlanet.designation.like('%' + search_expr + '%'))
    else:
        if search_form.dec_min.data:
            minor_planet_query = minor_planet_query.filter(MinorPlanet.cur_dec > (np.pi * search_form.dec_min.data / 180.0))
        if search_form.maglim.data:
            minor_planet_query = minor_planet_query.filter(MinorPlanet.eval_mag <= search_form.maglim.data)
        if search_form.season.data and search_form.season.data != 'All':
            minor_planet_query = minor_planet_query.join(Constellation) \
                                                   .filter(Constellation.season == search_form.season.data)

    order_by_field = get_order_by_field(sort_def, sort_by)

    if order_by_field is None:
        order_by_field = MinorPlanet.eval_mag

    minor_planets_for_render = minor_planet_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=minor_planet_query.count(), search=False, record_name='minor_planets',
                            css_framework='semantic', not_passed_args='back')

    return render_template('main/solarsystem/minor_planets.html', minor_planets=minor_planets_for_render, pagination=pagination,
                           search_form=search_form, table_sort=table_sort)


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>', methods=['GET', 'POST'])
@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/info', methods=['GET', 'POST'])
def minor_planet_info(minor_planet_id):
    """View a minor_planet info."""
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    form = MinorPlanetFindChartForm()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    mpc_minor_planet = get_all_mpc_minor_planets().iloc[minor_planet.int_designation - 1]

    body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

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

    minor_planet_ra_ang, minor_planet_dec_ang, distance = earth.at(t).observe(body).radec()
    minor_planet_ra = minor_planet_ra_ang.radians
    minor_planet_dec = minor_planet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            form.ra.data = minor_planet_ra
            form.dec.data = minor_planet_dec

    chart_control = common_prepare_chart_data(form)

    embed = request.args.get('embed')

    return render_template('main/solarsystem/minor_planet_info.html', fchart_form=form, type='info', minor_planet=minor_planet,
                           minor_planet_ra=minor_planet_ra, minor_planet_dec=minor_planet_dec, chart_control=chart_control,
                           trajectory=trajectory_b64, embed=embed)


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def minor_planet_chart_pos_img(minor_planet_id, ra, dec):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    minor_planet_ra = to_float(request.args.get('obj_ra'), None)
    minor_planet_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes, img_format = common_chart_pos_img(minor_planet_ra, minor_planet_dec, ra, dec, visible_objects=visible_objects, trajectory=trajectory)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def minor_planet_chart_legend_img(minor_planet_id, ra, dec):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    minor_planet_ra = to_float(request.args.get('obj_ra'), None)
    minor_planet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(minor_planet_ra, minor_planet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def minor_planet_chart_pdf(minor_planet_id, ra, dec):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    minor_planet_ra = to_float(request.args.get('obj_ra'), None)
    minor_planet_dec = to_float(request.args.get('obj_dec'), None)

    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pdf_img(minor_planet_ra, minor_planet_dec, ra, dec, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>')
@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/catalogue_data')
def minor_planet_catalogue_data(minor_planet_id):
    """View a minor_planet catalog info."""
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)
    return render_template('main/solarsystem/minor_planet_info.html', type='catalogue_data', minor_planet=minor_planet)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
