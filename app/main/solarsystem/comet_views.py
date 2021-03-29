import os
import numpy as np
import math
import threading
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

from .comet_forms import (
    SearchCometForm,
    CometFindChartForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_dso_list_menu,
)

from app.commons.utils import to_float

main_comet = Blueprint('main_comet', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 15/60, 30/60, 1, 2, 5, 10)

all_comets_expiration = datetime.now() + timedelta(days=1)
all_comets = None
creation_running = False


def _load_comet_brightness(all_comets, fname):
    with open(fname, 'r') as f:
        lines = f.readlines()
    for line in lines:
        comet_id, str_mag = line.split(' ')
        try:
            all_comets.loc[all_comets['comet_id'] == comet_id, 'mag'] = float(str_mag)
        except Exception:
            pass


def _create_comet_brighness_file(all_comets, fname):
    global creation_running
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    mags = []
    t = ts.now()
    with open(fname, 'w') as f:
        for index, row in all_comets.iterrows():
            m = 22.0
            try:
                comet = sun + mpc.comet_orbit(row, ts, GM_SUN)
                dist_earth = earth.at(t).observe(comet).distance().au
                dist_sun = sun.at(t).observe(comet).distance().au
                if (dist_earth<10.0):
                    m = row['magnitude_H'] + 5.0*np.log10(dist_earth) + 2.5*row['magnitude_G']*np.log10(dist_sun)
                    print('Comet: {} de={} ds={} m={} g={}'.format(row['designation'], dist_earth, dist_sun, m, row['magnitude_G']), flush=True)
            except Exception:
                pass
            f.write(row['comet_id'] + ' ' + str(m) + '\n')
            mags.append(m)

    all_comets['mag'] = mags
    creation_running = False

def _get_all_comets():
    global all_comets
    global all_comets_expiration
    global creation_running
    now = datetime.now()
    if all_comets is None or now > all_comets_expiration:
        all_comets_expiration = now + timedelta(days=1)
        with load.open(mpc.COMET_URL, reload=True) as f:
            all_comets = mpc.load_comets_dataframe_slow(f)
            all_comets = (all_comets.sort_values('reference')
                      .groupby('designation', as_index=False).last()
                      .set_index('designation', drop=False))
            all_comets['comet_id'] = np.where(all_comets['designation_packed'].isnull(), all_comets['designation'], all_comets['designation_packed'])
            all_comets['comet_id'] = all_comets['comet_id'].str.replace('/','')
            all_comets['comet_id'] = all_comets['comet_id'].str.replace(' ', '')

        fname = os.path.join(current_app.config.get('USER_DATA_DIR'), 'comets_brightness.txt')

        if (not os.path.isfile(fname) or datetime.fromtimestamp(os.path.getctime(fname)) > all_comets_expiration) and not creation_running:
            all_comets.loc[:,'mag'] = 22.0
            creation_running = True
            thread = threading.Thread(target=_create_comet_brighness_file, args=(all_comets, fname,))
            thread.start()
        else:
            _load_comet_brightness(all_comets, fname)

    return all_comets

@main_comet.route('/comets', methods=['GET', 'POST'])
def comets():
    """View comets."""
    search_form = SearchCometForm()

    ret, page = process_paginated_session_search('comet_search_page', [
        ('comet_search', search_form.q),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_comet.comets'))

    offset = (page - 1) * per_page
    comets = _get_all_comets()

    comets = comets[comets['mag'] < 17.0].sort_values(by=['mag'])

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"','')
        comets = comets.query('designation.str.contains("{}")'.format(search_expr))

    if len(comets) > 0:
        comets_for_render = comets.iloc[offset : offset + per_page]
    else:
        comets_for_render = comets

    pagination = Pagination(page=page, total=len(comets), search=False, record_name='comets', css_framework='semantic', not_passed_args='back')
    return render_template('main/solarsystem/comets.html', comets=comets_for_render, pagination=pagination, search_form=search_form)

def _find_comet(comet_id):
    all_comets = _get_all_comets()
    c = all_comets.loc[all_comets['comet_id'] == comet_id]
    return c.iloc[0] if len(c)>0 else None

@main_comet.route('/comet/<string:comet_id>', methods=['GET', 'POST'])
@main_comet.route('/comet/<string:comet_id>/info', methods=['GET', 'POST'])
def comet_info(comet_id):
    """View a comet info."""
    comet = _find_comet(comet_id)
    if comet is None:
        abort(404)

    form  = CometFindChartForm()

    chart_control = common_prepare_chart_data(form)

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    c = sun + mpc.comet_orbit(comet, ts, GM_SUN)

    if form.from_date.data is None or form.to_date.data is None or form.from_date.data > form.to_date.data:
        t = ts.now()
        comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
    else:
        comet_ra_ang = None
        comet_dec_ang = None
        d1 = date(form.from_date.data.year, form.from_date.data.month, form.from_date.data.day)
        d2 = date(form.to_date.data.year, form.to_date.data.month, form.to_date.data.day)
        # d1 = datetime.today + timedelta(days=-15)
        # d2 = datetime.today + timedelta(days=-15)
        if d1 != d2:
            trajectory = []
            while d1<=d2:
                t = ts.utc(d1.year, d1.month, d1.day)
                ra1, dec1, distance = earth.at(t).observe(c).radec()
                trajectory.append((ra1.radians, dec1.radians, ''))
                d1 += timedelta(days=1)
            t = ts.utc(d1.year, d1.month, d1.day)
            comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
        else:
            t = ts.utc(d1.year, d1.month, d1.day)
            comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()

    comet_ra = comet_ra_ang.radians
    comet_dec = comet_dec_ang.radians

    if form.ra.data is None:
        form.ra.data = comet_ra
    if form.dec.data is None:
        form.dec.data = comet_dec


    return render_template('main/solarsystem/comet_info.html', fchart_form=form, type='info', comet=comet, comet_ra=comet_ra, comet_dec=comet_dec, chart_control=chart_control, )


@main_comet.route('/comet/<string:comet_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def comet_chart_pos_img(comet_id, ra, dec):
    comet = _find_comet(comet_id)
    if comet is None:
        abort(404)

    comet_ra = to_float(request.args.get('obj_ra'), None)
    comet_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(comet_ra, comet_dec, ra, dec, visible_objects=visible_objects)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_comet.route('/comet/<string:comet_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def comet_chart_legend_img(comet_id, ra, dec):
    comet = _find_comet(comet_id)
    if comet is None:
        abort(404)

    comet_ra = to_float(request.args.get('obj_ra'), None)
    comet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(comet_ra, comet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_comet.route('/comet/<string:comet_id>')
@main_comet.route('/comet/<string:comet_id>/catalogue_data')
def comet_catalogue_data(comet_id):
    """View a comet catalog info."""
    comet = _find_comet(comet_id)
    if comet is None:
        abort(404)
    return render_template('main/solarsystem/comet_info.html', type='catalogue_data', user_descr=user_descr)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag

