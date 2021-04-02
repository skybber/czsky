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

from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search, get_items_per_page

from .asteroid_forms import (
    SearchAsteroidForm,
    AsteroidFindChartForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_dso_list_menu,
)

from app.commons.utils import to_float

main_asteroid = Blueprint('main_asteroid', __name__)

all_asteroids = None

def _get_all_asteroids():
    global all_asteroids
    if all_asteroids is None:
        with load.open('data/MPCORB.9999.DAT') as f:
            all_asteroids = mpc.load_mpcorb_dataframe(f)
            bad_orbits = all_asteroids.semimajor_axis_au.isnull()
            all_asteroids = all_asteroids[~bad_orbits]
            all_asteroids['asteroid_id'] = all_asteroids['designation_packed']
    return all_asteroids

@main_asteroid.route('/asteroids', methods=['GET', 'POST'])
def asteroids():
    """View asteroids."""
    search_form = SearchAsteroidForm()

    ret, page = process_paginated_session_search('asteroid_search_page', [
        ('asteroid_search', search_form.q),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_asteroid.asteroids'))

    offset = (page - 1) * per_page
    asteroids = _get_all_asteroids()

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"','')
        asteroids = asteroids.query('designation.str.contains("{}")'.format(search_expr))

    if len(asteroids) > 0:
        asteroids_for_render = asteroids.iloc[offset : offset + per_page]
    else:
        asteroids_for_render = asteroids

    pagination = Pagination(page=page, total=len(asteroids), search=False, record_name='asteroids', css_framework='semantic', not_passed_args='back')
    return render_template('main/solarsystem/asteroids.html', asteroids=asteroids_for_render, pagination=pagination, search_form=search_form)

def _find_asteroid(asteroid_id):
    all_asteroids = _get_all_asteroids()
    c = all_asteroids.loc[all_asteroids['asteroid_id'] == asteroid_id]
    return c.iloc[0] if len(c)>0 else None

@main_asteroid.route('/asteroid/<string:asteroid_id>', methods=['GET', 'POST'])
@main_asteroid.route('/asteroid/<string:asteroid_id>/info', methods=['GET', 'POST'])
def asteroid_info(asteroid_id):
    """View a asteroid info."""
    asteroid = _find_asteroid(asteroid_id)
    if asteroid is None:
        abort(404)

    form  = AsteroidFindChartForm()

    chart_control = common_prepare_chart_data(form)

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    c = sun + mpc.mpcorb_orbit(asteroid, ts, GM_SUN)

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    if (form.date_from.data is None) or (form.date_to.data is None) or form.date_from.data >= form.date_to.data:
        t = ts.now()
        asteroid_ra_ang, asteroid_dec_ang, distance = earth.at(t).observe(c).radec()
        trajectory_b64 = None
    else:
        d1 = date(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = date(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        t = ts.now()
        asteroid_ra_ang, asteroid_dec_ang, distance = earth.at(t).observe(c).radec()
        if d1 != d2:
            trajectory = []
            while d1<=d2:
                t = ts.utc(d1.year, d1.month, d1.day)
                ra, dec, distance = earth.at(t).observe(c).radec()
                trajectory.append((ra.radians, dec.radians, d1.strftime('%d.%m.')))
                d1 += timedelta(days=1)
            t = ts.utc(d1.year, d1.month, d1.day)
            trajectory_json = json.dumps(trajectory)
            trajectory_b64 = base64.b64encode(trajectory_json.encode('utf-8'))
        else:
            trajectory_b64 = None

    asteroid_ra = asteroid_ra_ang.radians
    asteroid_dec = asteroid_dec_ang.radians

    form.ra.data = asteroid_ra
    form.dec.data = asteroid_dec

    return render_template('main/solarsystem/asteroid_info.html', fchart_form=form, type='info', asteroid=asteroid, asteroid_ra=asteroid_ra, asteroid_dec=asteroid_dec,
                           chart_control=chart_control, trajectory=trajectory_b64)


@main_asteroid.route('/asteroid/<string:asteroid_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def asteroid_chart_pos_img(asteroid_id, ra, dec):
    asteroid = _find_asteroid(asteroid_id)
    if asteroid is None:
        abort(404)

    asteroid_ra = to_float(request.args.get('obj_ra'), None)
    asteroid_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pos_img(asteroid_ra, asteroid_dec, ra, dec, visible_objects=visible_objects, trajectory=trajectory)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_asteroid.route('/asteroid/<string:asteroid_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def asteroid_chart_legend_img(asteroid_id, ra, dec):
    asteroid = _find_asteroid(asteroid_id)
    if asteroid is None:
        abort(404)

    asteroid_ra = to_float(request.args.get('obj_ra'), None)
    asteroid_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(asteroid_ra, asteroid_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_asteroid.route('/asteroid/<string:asteroid_id>')
@main_asteroid.route('/asteroid/<string:asteroid_id>/catalogue_data')
def asteroid_catalogue_data(asteroid_id):
    """View a asteroid catalog info."""
    asteroid = _find_asteroid(asteroid_id)
    if asteroid is None:
        abort(404)
    return render_template('main/solarsystem/asteroid_info.html', type='catalogue_data', user_descr=user_descr)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
