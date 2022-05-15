import os
import numpy as np
import math
import threading
import json
import base64

from datetime import date, datetime, timedelta

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import db

from app.models import MinorPlanet
from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search, get_items_per_page

from .minor_planet_forms import (
    SearchMinorPlanetForm,
    MinorPlanetFindChartForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    get_trajectory_time_delta,
    common_ra_dec_fsz_from_request,
)

from app.commons.utils import to_float

main_minor_planet = Blueprint('main_minor_planet', __name__)

all_minor_planets = None


def _get_mpc_minor_planets():
    global all_minor_planets
    if all_minor_planets is None:
        with load.open('data/MPCORB.9999.DAT') as f:
            all_minor_planets = mpc.load_mpcorb_dataframe(f)
            bad_orbits = all_minor_planets.semimajor_axis_au.isnull()
            all_minor_planets = all_minor_planets[~bad_orbits]
            all_minor_planets['minor_planet_id'] = all_minor_planets['designation_packed']
    return all_minor_planets


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


@main_minor_planet.route('/minor_planets', methods=['GET', 'POST'])
def minor_planets():
    """View minor_planets."""
    search_form = SearchMinorPlanetForm()

    ret, page = process_paginated_session_search('minor_planet_search_page', [
        ('minor_planet_search', search_form.q),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_minor_planet.minor_planets'))

    offset = (page - 1) * per_page
    minor_planet_query = MinorPlanet.query

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"', '')
        minor_planet_query = minor_planet_query.filter(MinorPlanet.designation.like('%' + search_expr + '%'))

    magnitudes = {}

    minor_planets_for_render = minor_planet_query.order_by(MinorPlanet.int_designation).limit(per_page).offset(offset).all()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    t = ts.now()

    ra, dec, earth_sun_distance = earth.at(t).observe(sun).apparent().radec()

    mpc_minor_planets = _get_mpc_minor_planets()

    for minor_planet in minor_planets_for_render:
        mpc_minor_planet = mpc_minor_planets.iloc[minor_planet.int_designation]
        body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)
        ra, dec, sun_body_distance = sun.at(t).observe(body).radec()
        ra, dec, earth_body_distance = earth.at(t).observe(body).apparent().radec()

        apparent_magnitude = _get_apparent_magnitude_hg(minor_planet.magnitude_H, minor_planet.magnitude_G, earth_body_distance.au, sun_body_distance.au, earth_sun_distance.au)
        if apparent_magnitude:
            magnitudes[minor_planet.int_designation] = '{:.2f}'.format(apparent_magnitude)

    pagination = Pagination(page=page, per_page=per_page, total=minor_planet_query.count(), search=False, record_name='minor_planets', css_framework='semantic', not_passed_args='back')
    return render_template('main/solarsystem/minor_planets.html', minor_planets=minor_planets_for_render, pagination=pagination, search_form=search_form, magnitudes=magnitudes)


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>', methods=['GET', 'POST'])
@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/info', methods=['GET', 'POST'])
def minor_planet_info(minor_planet_id):
    """View a minor_planet info."""
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    form = MinorPlanetFindChartForm()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    mpc_minor_planet = _get_mpc_minor_planets().iloc[minor_planet.int_designation-1]

    c = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    if (form.date_from.data is None) or (form.date_to.data is None) or form.date_from.data >= form.date_to.data:
        t = ts.now()
        minor_planet_ra_ang, minor_planet_dec_ang, distance = earth.at(t).observe(c).radec()
        trajectory_b64 = None
    else:
        d1 = date(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = date(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        t = ts.now()
        minor_planet_ra_ang, minor_planet_dec_ang, distance = earth.at(t).observe(c).radec()
        if d1 != d2:
            time_delta = d2 - d1
            if time_delta.days > 365:
                d2 = d1 + timedelta(days=365)
            dt = get_trajectory_time_delta(d1, d2)
            trajectory = []
            while d1 <= d2:
                t = ts.utc(d1.year, d1.month, d1.day)
                ra, dec, distance = earth.at(t).observe(c).radec()
                trajectory.append((ra.radians, dec.radians, d1.strftime('%d.%m.')))
                if d1 == d2:
                    break
                d1 += dt # timedelta(days=1)
                if d1 > d2:
                    d1 = d2
            t = ts.utc(d1.year, d1.month, d1.day)
            trajectory_json = json.dumps(trajectory)
            trajectory_b64 = base64.b64encode(trajectory_json.encode('utf-8'))
        else:
            trajectory_b64 = None

    minor_planet_ra = minor_planet_ra_ang.radians
    minor_planet_dec = minor_planet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        form.ra.data = minor_planet_ra
        form.dec.data = minor_planet_dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/solarsystem/minor_planet_info.html', fchart_form=form, type='info', minor_planet=minor_planet, minor_planet_ra=minor_planet_ra, minor_planet_dec=minor_planet_dec,
                           chart_control=chart_control, trajectory=trajectory_b64)


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
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

    img_bytes = common_chart_pos_img(minor_planet_ra, minor_planet_dec, ra, dec, visible_objects=visible_objects, trajectory=trajectory)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def minor_planet_chart_legend_img(minor_planet_id, ra, dec):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    minor_planet_ra = to_float(request.args.get('obj_ra'), None)
    minor_planet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(minor_planet_ra, minor_planet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
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


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>')
@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/catalogue_data')
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
