import os
import numpy as np
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
from flask_rq import get_queue

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import db
from app import create_app

from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search, get_items_per_page
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
    common_chart_pdf_img,
    get_trajectory_time_delta,
    common_ra_dec_fsz_from_request,
)

from app.commons.comet_loader import import_update_comets, update_comets_cobs_observations, update_evaluated_comet_brightness, update_comets_positions
from app.commons.utils import to_float

from app.models import (
    Comet,
    CometObservation,
    Constellation,
)

main_comet = Blueprint('main_comet', __name__)

all_comets_expiration = datetime.now() + timedelta(days=1)
all_comets = None


def _update_comets_cobs_observations():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        update_comets_cobs_observations()


def _update_evaluated_comet_brightness():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        update_evaluated_comet_brightness()


def _update_comets_positions():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        update_comets_positions()


job1 = scheduler.add_job(_update_comets_cobs_observations, 'interval', hours=12, replace_existing=True)
job2 = scheduler.add_job(_update_evaluated_comet_brightness, 'interval', days=5, replace_existing=True)
job3 = scheduler.add_job(_update_comets_positions, 'interval', hours=3, replace_existing=True)


def _get_mag_coma_from_observations(observs):
    mag, coma_diameter = None, None
    if len(observs) > 0:
        n = 1
        mag = observs[0].mag
        coma_diameter = observs[0].coma_diameter
        first_dt = observs[0].date
        for o in observs[1:5]:
            if (first_dt - o.date).days > 2:
                break
            n += 1
            mag += o.mag
            if o.coma_diameter is not None:
                coma_diameter = (coma_diameter + o.coma_diameter) if coma_diameter is not None else o.coma_diameter
        if mag is not None:
            mag = mag / n
        if coma_diameter is not None:
            coma_diameter = coma_diameter / n

    return mag, coma_diameter


def get_all_comets():
    global all_comets
    global all_comets_expiration
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

        for comet in Comet.query.filter_by().all():
            after = datetime.today() - timedelta(days=31)
            mag, coma_diameter = comet.eval_mag, None
            real_mag = False
            observs = CometObservation.query.filter_by(comet_id=comet.id) \
                .filter(CometObservation.date >= after) \
                .order_by(CometObservation.date.desc()).all()[:5]

            comet_id = comet.comet_id
            if len(observs) > 0:
                mag, coma_diameter = _get_mag_coma_from_observations(observs)
                current_app.logger.info('Setup comet mag from COBS comet={} mag={} coma_diameter={}'.format(comet_id, mag, coma_diameter))
                real_mag = True
            try:
                all_comets.loc[all_comets['comet_id'] == comet_id, 'mag'] = float('{:.1f}'.format(mag)) if mag else None
                all_comets.loc[all_comets['comet_id'] == comet_id, 'coma_diameter'] = '{:.1f}\''.format(coma_diameter) if coma_diameter else '-'
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_ra'] = comet.cur_ra_str_short()
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_dec'] = comet.cur_dec_str_short()
                constell = Constellation.get_constellation_by_id(comet.cur_constell_id)
                all_comets.loc[all_comets['comet_id'] == comet_id, 'cur_constell'] = constell.iau_code if constell is not None else ''
                all_comets.loc[all_comets['comet_id'] == comet_id, 'real_mag'] = real_mag
            except Exception:
                pass

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
        d1 = datetime(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
        d2 = datetime(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
        t = ts.now()
        comet_ra_ang, comet_dec_ang, distance = earth.at(t).observe(c).radec()
        if d1 != d2:
            time_delta = d2 - d1
            if time_delta.days > 365:
                d2 = d1 + timedelta(days=365)
            dt, hr_step = get_trajectory_time_delta(d1, d2)
            trajectory = []
            hr_count = 0
            while d1 <= d2:
                t = ts.utc(d1.year, d1.month, d1.day, d1.hour)
                ra, dec, distance = earth.at(t).observe(c).radec()
                fmt = '%d.%m.' if (hr_count % 24) == 0 else '%H:00'
                trajectory.append((ra.radians, dec.radians, d1.strftime(fmt)))
                d1 += dt
                hr_count += hr_step
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
        last_mag, last_coma_diameter = _get_mag_coma_from_observations(cobs_observations)

    if last_mag is not None:
        last_mag = '{:.2f}'.format(last_mag)
    else:
        last_mag = '-'

    if last_coma_diameter is not None:
        last_coma_diameter = '{:.2f}'.format(last_coma_diameter)
    else:
        last_coma_diameter = '-'

    return render_template('main/solarsystem/comet_info.html', type='cobs_observations', comet=comet, last_mag=last_mag,
                           last_coma_diameter=last_coma_diameter, cobs_observations=enumerate(page_items),
                           page_offset=page_offset, pagination=pagination, search_form=search_form)


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
