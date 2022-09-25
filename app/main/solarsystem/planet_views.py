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
from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from .planet_forms import (
    PlanetFindChartForm,
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
from app.commons.planet_utils import get_all_planets, Planet

main_planet = Blueprint('main_planet', __name__)


@main_planet.route('/planets', methods=['GET', 'POST'])
def planets():
    planets = get_all_planets()
    return render_template('main/solarsystem/planets.html', planets_enumerate=enumerate(planets))


def _find_planet(planet_name):
    planets = get_all_planets()
    planet_name_lower = planet_name.lower()
    return next(p for p in planets if p.name == planet_name)


@main_planet.route('/planet/<string:planet_name>', methods=['GET', 'POST'])
@main_planet.route('/planet/<string:planet_name>/info', methods=['GET', 'POST'])
def planet_info(planet_name):
    """View a planet info."""
    planet = _find_planet(planet_name)
    if planet is None:
        abort(404)

    form = PlanetFindChartForm()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    if (form.date_from.data is None) or (form.date_to.data is None) or form.date_from.data >= form.date_to.data:
        t = ts.now()
        planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()
        trajectory_b64 = None
    else:
        d1 = date(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = date(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        t = ts.now()
        planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()
        if d1 != d2:
            time_delta = d2 - d1
            if time_delta.days > 365:
                d2 = d1 + timedelta(days=365)
            dt, hr_step = get_trajectory_time_delta(d1, d2)
            trajectory = []
            while d1 <= d2:
                t = ts.utc(d1.year, d1.month, d1.day)
                ra, dec, distance = earth.at(t).observe(planet.eph).radec()
                trajectory.append((ra.radians, dec.radians, d1.strftime('%d.%m.')))
                if d1 == d2:
                    break
                d1 += dt  # timedelta(days=1)
                if d1 > d2:
                    d1 = d2
            t = ts.utc(d1.year, d1.month, d1.day)
            trajectory_json = json.dumps(trajectory)
            trajectory_b64 = base64.b64encode(trajectory_json.encode('utf-8'))
        else:
            trajectory_b64 = None

    planet_ra = planet_ra_ang.radians
    planet_dec = planet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            form.ra.data = planet_ra
            form.dec.data = planet_dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/solarsystem/planet_info.html', fchart_form=form, type='info', planet=planet,
                           planet_ra=planet_ra, planet_dec=planet_dec, chart_control=chart_control, trajectory=trajectory_b64)


@main_planet.route('/planet/<string:planet_name>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_pos_img(planet_name, ra, dec):
    planet = _find_planet(planet_name)
    if planet is None:
        abort(404)

    planet_ra = to_float(request.args.get('obj_ra'), None)
    planet_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes, img_format = common_chart_pos_img(planet_ra, planet_dec, ra, dec, visible_objects=visible_objects,
                                                 trajectory=trajectory)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_planet.route('/planet/<string:planet_name>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_legend_img(planet_name, ra, dec):
    planet = _find_planet(planet_name)
    if planet is None:
        abort(404)

    planet_ra = to_float(request.args.get('obj_ra'), None)
    planet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(planet_ra, planet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_planet.route('/planet/<string:planet_name>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_pdf(planet_name, ra, dec):
    planet = _find_planet(planet_name)
    if planet is None:
        abort(404)

    planet_ra = to_float(request.args.get('obj_ra'), None)
    planet_dec = to_float(request.args.get('obj_dec'), None)

    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pdf_img(planet_ra, planet_dec, ra, dec, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_planet.route('/planet/<string:planet_name>')
@main_planet.route('/planet/<string:planet_name>/catalogue_data')
def planet_catalogue_data(planet_name):
    """View a planet catalog info."""
    planet = _find_planet(planet_name)
    if planet is None:
        abort(404)
    return render_template('main/solarsystem/planet_info.html', type='catalogue_data', user_descr=user_descr)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
