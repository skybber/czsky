import os
import numpy as np
import math
import threading
import json
import base64
from io import BytesIO

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
    common_chart_pdf_img,
    get_trajectory_time_delta,
    common_ra_dec_fsz_from_request,
)

from app.commons.comet_loader import import_update_comets
from app.commons.utils import to_float

from app.models import (
    Comet,
    CometObservation
)

main_comet = Blueprint('main_comet', __name__)

all_comets_expiration = datetime.now() + timedelta(days=1)
all_comets = None
creation_running = False


def _load_comet_brightness(all_comets, fname):
    with open(fname, 'r') as f:
        lines = f.readlines()
    for line in lines:
        comet_id, str_mag = line.split(' ')
        after = datetime.today() - timedelta(days=31)
        comet = Comet.query.filter_by(comet_id=comet_id).first()
        str_coma_diameter = '-'
        if comet:
            obsers = CometObservation.query.filter_by(comet_id=comet.id)\
                .filter(CometObservation.date >= after) \
                .order_by(CometObservation.date.desc()).all()[:5]
            if len(obsers) > 0:
                n = 1
                mag = obsers[0].mag
                coma_diameter = obsers[0].coma_diameter
                first_dt = obsers[0].date
                for o in obsers[1:]:
                    if (first_dt - o.date).days > 2:
                        break
                    n += 1
                    mag += o.mag
                    if o.coma_diameter is not None:
                        coma_diameter = (coma_diameter + o.coma_diameter) if coma_diameter is not None else o.coma_diameter
                str_mag = '{:.1f}'.format(mag / n)
                str_coma_diameter = '{:.1f}\''.format(coma_diameter / n) if coma_diameter is not None else '-'
                current_app.logger.info('Setup comet mag from COBS comet={} mag={} coma_diameter={}'.format(comet_id, str_mag, str_coma_diameter))
        try:
            all_comets.loc[all_comets['comet_id'] == comet_id, 'mag'] = float(str_mag)
            all_comets.loc[all_comets['comet_id'] == comet_id, 'coma_diameter'] = str_coma_diameter
        except Exception:
            pass


def _create_comet_evaluated_brighness_file(all_comets, fname):
    global creation_running
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    mags = []
    t = ts.now()
    with open(fname, 'w') as f:
        for index, mpc_comet in all_comets.iterrows():
            m = 22.0
            try:
                skf_comet = sun + mpc.comet_orbit(mpc_comet, ts, GM_SUN)
                dist_earth = earth.at(t).observe(skf_comet).distance().au
                dist_sun = sun.at(t).observe(skf_comet).distance().au
                if dist_earth < 10.0:
                    m = mpc_comet['magnitude_g'] + 5.0*np.log10(dist_earth) + 2.5*mpc_comet['magnitude_k']*np.log10(dist_sun)
                    print('Comet: {} de={} ds={} m={} g={}'.format(mpc_comet['designation'], dist_earth, dist_sun, m, mpc_comet['magnitude_k']), flush=True)

            except Exception:
                pass
            f.write(mpc_comet['comet_id'] + ' ' + str(m) + '\n')
            mags.append(m)

    all_comets['mag'] = mags
    creation_running = False


def get_all_comets():
    global all_comets
    global all_comets_expiration
    global creation_running
    now = datetime.now()
    if all_comets is None or now > all_comets_expiration:
        all_comets_expiration = now + timedelta(days=1)
        with load.open(mpc.COMET_URL, reload=True) as f:
            # fix problem in coma in CometEls.txt
            lines = f.readlines()
            s = ''
            for line in lines:
                s += line.decode('ascii').replace(',', ' ')
            sio = BytesIO(s.encode('ascii'))
            # end of fix
            all_comets = mpc.load_comets_dataframe_slow(sio)
            all_comets = (all_comets.sort_values('reference')
                          .groupby('designation', as_index=False).last()
                          .set_index('designation', drop=False))
            all_comets['comet_id'] = np.where(all_comets['designation_packed'].isnull(), all_comets['designation'], all_comets['designation_packed'])
            all_comets['comet_id'] = all_comets['comet_id'].str.replace('/', '')
            all_comets['comet_id'] = all_comets['comet_id'].str.replace(' ', '')

            import_update_comets(all_comets, False)

        # brightness file expires after 5 days
        fname = os.path.join(current_app.config.get('USER_DATA_DIR'), 'comets_brightness.txt')

        if (not os.path.isfile(fname) or datetime.fromtimestamp(os.path.getctime(fname)) + timedelta(days=5) < all_comets_expiration) and not creation_running:
            all_comets.loc[:, 'mag'] = 22.0
            creation_running = True
            thread = threading.Thread(target=_create_comet_evaluated_brighness_file, args=(all_comets, fname,))
            thread.start()
        else:
            _load_comet_brightness(all_comets, fname)
    return all_comets


def find_mpc_comet(comet_id):
    all_comets = get_all_comets()
    c = all_comets.loc[all_comets['comet_id'] == comet_id]
    return c.iloc[0] if len(c) > 0 else None


@main_comet.route('/comets', methods=['GET', 'POST'])
def comets():
    """View comets."""
    search_form = SearchCometForm()

    ret, page, _ = process_paginated_session_search('comet_search_page', None, [
        ('comet_search', search_form.q),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_comet.comets'))

    offset = (page - 1) * per_page
    comets = get_all_comets()
    comets = comets[comets['mag'] < 20.0].sort_values(by=['mag'])

    if search_form.q.data:
        search_expr = search_form.q.data.replace('"', '')
        comets = comets.query('designation.str.contains("{}")'.format(search_expr))

    if len(comets) > 0:
        comets_for_render = comets.iloc[offset:offset + per_page]
    else:
        comets_for_render = comets

    pagination = Pagination(page=page, per_page=per_page, total=len(comets), search=False, record_name='comets', css_framework='semantic', not_passed_args='back')
    return render_template('main/solarsystem/comets.html', comets=comets_for_render, pagination=pagination, search_form=search_form)


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

    c = sun + mpc.comet_orbit(comet, ts, GM_SUN)

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    if (form.date_from.data is None) or (form.date_to.data is None) or form.date_from.data >= form.date_to.data:
        t = ts.now()
        comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
        trajectory_b64 = None
    else:
        d1 = date(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = date(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        t = ts.now()
        comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
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
                d1 += dt
            t = ts.utc(d1.year, d1.month, d1.day)
            trajectory_json = json.dumps(trajectory)
            trajectory_b64 = base64.b64encode(trajectory_json.encode('utf-8'))
        else:
            trajectory_b64 = None

    comet_ra = comet_ra_ang.radians
    comet_dec = comet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        form.ra.data = comet_ra
        form.dec.data = comet_dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/solarsystem/comet_info.html', fchart_form=form, type='info', comet=comet, comet_ra=comet_ra, comet_dec=comet_dec,
                           chart_control=chart_control, trajectory=trajectory_b64)


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

    img_bytes = common_chart_pos_img(comet_ra, comet_dec, ra, dec, visible_objects=visible_objects, trajectory=trajectory)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


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
