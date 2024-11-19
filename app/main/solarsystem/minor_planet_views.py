import numpy as np
import os
import math
import json
import base64
import requests
import gzip
import uuid

from datetime import date, datetime, timedelta
import datetime as dt_module

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

from flask_login import current_user

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import create_app, csrf, db, scheduler

from app.models import (
    DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY,
    Constellation,
    MinorPlanet,
    Observation,
    ObservationTargetType,
)

from app.commons.dso_utils import CHART_MINOR_PLANET_PREFIX

from app.commons.pagination import Pagination
from app.commons.search_utils import (
    process_paginated_session_search,
    get_items_per_page,
    create_table_sort,
    get_order_by_field,
)

from .minor_planet_forms import (
    SearchMinorPlanetForm,
    MinorPlanetFindChartForm,
)

from app.main.forms import ObservationLogNoFilterForm
from app.main.chart.chart_forms import ChartForm

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_prepare_date_from_to,
    common_chart_pdf_img,
    common_ra_dec_fsz_from_request,
    get_trajectory_b64,
)

from app.commons.utils import to_float, is_splitview_supported
from app.commons.minor_planet_utils import get_all_mpc_minor_planets, update_minor_planets_positions, update_minor_planets_brightness
from app.commons.observing_session_utils import find_observing_session, show_observation_log, combine_observing_session_date_time
from app.commons.observation_form_utils import assign_equipment_choices

from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.commons.coordinates import ra_to_str, dec_to_str
from app.commons.solar_system_chart_utils import AU_TO_KM

utc = dt_module.timezone.utc

main_minor_planet = Blueprint('main_minor_planet', __name__)


def _update_minor_planet_positions():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY, timedelta(hours=1)):
            update_minor_planets_positions()
            update_minor_planets_brightness()


def _download_mpcorb_dat():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_MINOR_PLANETS_POS_BRIGHT_KEY, timedelta(hours=1)):
            data_dir = os.path.join(os.getcwd(), 'data/')
            url = "https://minorplanetcenter.net/iau/MPCORB/MPCORB.DAT.gz"
            gz_file_path = data_dir + f"MPCORB.DAT.{uuid.uuid4().hex}.gz"
            output_tmp_file_path = data_dir + f"MPCORB.9999.DAT.{uuid.uuid4().hex}.tmp"
            output_file_path = data_dir + "MPCORB.9999.DAT"

            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(gz_file_path, 'wb') as f:
                    f.write(response.raw.read())
                with gzip.open(gz_file_path, 'rt') as gz_file:
                    with open(output_tmp_file_path, 'w') as output_file:
                        for current_row, line in enumerate(gz_file, start=1):
                            if current_row >= 44:
                                output_file.write(line)
                            if current_row >= 10042:
                                break
                os.rename(output_tmp_file_path, output_file_path)
                os.remove(gz_file_path)
                current_app.logger.info('File MPCORB.9999.DAT updated.')
            else:
                current_app.logger.error('Download MPCORB.DAT.gz failed. url={}'.format(url))


job1 = scheduler.add_job(_update_minor_planet_positions, 'cron', hour=14, replace_existing=True, jitter=60)

job2 = scheduler.add_job(_download_mpcorb_dat, 'cron', day='1,8,15,22', hour=13, replace_existing=True, jitter=60)


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


class MinorPlanetData:
    def __init__(self, orbit_period, ra, dec, mag, distance):
        self.orbit_period = orbit_period
        self.ra = ra
        self.dec = dec
        self.mag = mag
        self.distance_au = distance / AU_TO_KM
        self.distance = distance

    def ra_str(self):
        return ra_to_str(self.ra)

    def dec_str(self):
        return dec_to_str(self.dec)

    def angular_diameter_seconds(self):
        return self.angular_diameter * 180.0 * 60 * 60 / math.pi


@main_minor_planet.route('/minor-planets', methods=['GET', 'POST'])
def minor_planets():
    """View minor_planets."""
    search_form = SearchMinorPlanetForm()

    sort_def = { 'designation': MinorPlanet.designation,
                 'cur_ra': MinorPlanet.cur_ra,
                 'cur_dec': MinorPlanet.cur_dec,
                 'cur_angular_dist_from_sun': MinorPlanet.cur_angular_dist_from_sun,
                 'constellation': MinorPlanet.cur_constell_id,
                 'eval_mag': MinorPlanet.eval_mag,
                 }

    ret, page, sort_by = process_paginated_session_search('minor_planet_search_page', 'minor_planet_sort_by', [
        ('minor_planet_search', search_form.q),
        ('minor_planet_season', search_form.season),
        ('minor_planet_maglim', search_form.maglim),
        ('dec_min', search_form.dec_min),
        ('angular_dist_from_sun_min', search_form.angular_dist_from_sun_min),
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
        if search_form.angular_dist_from_sun_min.data:
            minor_planet_query = minor_planet_query.filter(MinorPlanet.cur_angular_dist_from_sun > (np.pi * search_form.angular_dist_from_sun_min.data / 180.0))
        if search_form.season.data and search_form.season.data != 'All':
            minor_planet_query = minor_planet_query.join(Constellation) \
                                                   .filter(Constellation.season == search_form.season.data)

    order_by_field = get_order_by_field(sort_def, sort_by)

    if order_by_field is None:
        order_by_field = MinorPlanet.eval_mag

    minor_planets_for_render = minor_planet_query.order_by(order_by_field).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=minor_planet_query.count(), search=False, record_name='minor_planets',
                            css_framework='semantic', not_passed_args='back')

    return render_template('main/solarsystem/minor_planets.html', type='list', minor_planets=minor_planets_for_render,
                           pagination=pagination, search_form=search_form, table_sort=table_sort, )


@main_minor_planet.route('/minor-planets/chart', methods=['GET', 'POST'])
@csrf.exempt
def minor_planets_chart():
    form = ChartForm()

    minor_planet = MinorPlanet.query.filter(MinorPlanet.eval_mag < 9).order_by('eval_mag').first()

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            if minor_planet:
                form.ra.data = minor_planet.cur_ra
                form.dec.data = minor_planet.cur_dec

    default_chart_iframe_url = None
    if minor_planet:
        default_chart_iframe_url = url_for('main_minor_planet.minor_planet_seltab', minor_planet_id=minor_planet.int_designation, embed='minor_planets', allow_back='false')

    chart_control = common_prepare_chart_data(form)

    return render_template('main/solarsystem/minor_planets.html', type='chart', fchart_form=form, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url)


@main_minor_planet.route('/minor-planets/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def minor_planets_chart_pos_img(ra, dec):
    minor_planets = MinorPlanet.query.filter(MinorPlanet.eval_mag < 13.0).all()

    highlights_pos_list = [(x.cur_ra, x.cur_dec, CHART_MINOR_PLANET_PREFIX + str(x.id), x.designation, x.eval_mag) for x in minor_planets if minor_planets]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_minor_planet.route('/minor-planets/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def minor_planets_chart_legend_img(ra, dec):
    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_minor_planet.route('/minor-planets/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def minor_planets_chart_pdf(ra, dec):
    minor_planets = MinorPlanet.query.filter(MinorPlanet.eval_mag < 12.0).all()
    highlights_pos_list = [(x.cur_ra, x.cur_dec, CHART_MINOR_PLANET_PREFIX + str(x.id), x.designation, x.eval_mag) for x in minor_planets if minor_planets]

    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/seltab')
def minor_planet_seltab(minor_planet_id):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    seltab = request.args.get('seltab', None)
    embed = request.args.get('embed')

    if not seltab and request.args.get('embed'):
        seltab = session.get('minor_planet_embed_seltab', None)

    if seltab == 'catalogue_data' or not seltab and embed == 'minor_planets':
        return _do_redirect('main_minor_planet.minor_planet_catalogue_data', minor_planet)

    if show_observation_log():
        return _do_redirect('main_minor_planet.minor_planet_observation_log', minor_planet)

    if is_splitview_supported():
        return _do_redirect('main_minor_planet.minor_planet_info', minor_planet, splitview=True)

    return _do_redirect('main_minor_planet.minor_planet_info', minor_planet)


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>', methods=['GET', 'POST'])
@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/info', methods=['GET', 'POST'])
@csrf.exempt
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
    if embed:
        session['minor_planet_embed_seltab'] = 'info'

    show_obs_log = show_observation_log()

    default_chart_iframe_url = url_for('main_minor_planet.minor_planet_catalogue_data', minor_planet_id=minor_planet_id,
                                       back=request.args.get('back'), back_id=request.args.get('back_id'),
                                       embed='minor_planets', allow_back='false')

    return render_template('main/solarsystem/minor_planet_info.html', fchart_form=form, type='info', minor_planet=minor_planet,
                           minor_planet_ra=minor_planet_ra, minor_planet_dec=minor_planet_dec, chart_control=chart_control,
                           trajectory=trajectory_b64, embed=embed, show_obs_log=show_obs_log, default_chart_iframe_url=default_chart_iframe_url)


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

    # minor_planet_ra = to_float(request.args.get('obj_ra'), None)
    # minor_planet_dec = to_float(request.args.get('obj_dec'), None)

    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pdf_img(None, None, ra, dec, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_minor_planet.route('/minor-planet/<string:minor_planet_id>')
@main_minor_planet.route('/minor-planet/<string:minor_planet_id>/catalogue_data')
def minor_planet_catalogue_data(minor_planet_id):
    """View a minor_planet catalog info."""
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    mpc_minor_planet = get_all_mpc_minor_planets().iloc[minor_planet.int_designation - 1]

    body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    t = ts.now()

    minor_planet_ra_ang, minor_planet_dec_ang, distance = earth.at(t).observe(body).radec()
    mp_ra = minor_planet_ra_ang.radians
    mp_dec = minor_planet_dec_ang.radians
    mp_distance_km = distance.au * AU_TO_KM

    minor_planet_data = MinorPlanetData(1000, mp_ra, mp_dec, minor_planet.eval_mag, mp_distance_km)

    embed = request.args.get('embed')
    if embed:
        session['minor_planet_embed_seltab'] = 'catalogue_data'

    show_obs_log = show_observation_log()

    return render_template('main/solarsystem/minor_planet_info.html', type='catalogue_data', minor_planet=minor_planet,
                           minor_planet_data=minor_planet_data, embed=embed, show_obs_log=show_obs_log)


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/observation-log', methods=['GET', 'POST'])
def minor_planet_observation_log(minor_planet_id):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    form = ObservationLogNoFilterForm()
    assign_equipment_choices(form, False)
    observation = observing_session.find_observation_by_minor_planet_id(minor_planet.id)
    is_new_observation_log = observation is None

    if is_new_observation_log:
        date_from = datetime.now()
        if date_from.date() != observing_session.date_from.date() and date_from.date() != observing_session.date_to.date():
            date_from = observing_session.date_from
        observation = Observation(
            observing_session_id=observing_session.id,
            target_type=ObservationTargetType.M_PLANET,
            minor_planet_id=minor_planet.id,
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
            observation.telescope_id = form.telescope.data if form.telescope.data != -1 else None
            observation.eyepiece_id = form.eyepiece.data if form.eyepiece.data != -1 else None
            observation.date_from = combine_observing_session_date_time(observing_session, form.date_from.data, form.time_from.data)
            observation.update_by = current_user.id
            observation.update_date = datetime.now()
            db.session.add(observation)
            db.session.commit()
            flash('Observation log successfully updated', 'form-success')
            return redirect(url_for('main_minor_planet.minor_planet_observation_log', minor_planet_id=minor_planet_id, back=back, back_id=back_id, embed=request.args.get('embed')))
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
        session['minor_planet_embed_seltab'] = 'obs_log'

    return render_template('main/solarsystem/minor_planet_info.html', type='observation_log', minor_planet=minor_planet, form=form,
                           embed=embed, is_new_observation_log=is_new_observation_log, observing_session=observing_session,
                           back=back, back_id=back_id, has_observations=False, show_obs_log=True,
                           )


@main_minor_planet.route('/minor_planet/<string:minor_planet_id>/observation-log-delete', methods=['GET', 'POST'])
def minor_planet_observation_log_delete(minor_planet_id):
    minor_planet = MinorPlanet.query.filter_by(int_designation=minor_planet_id).first()
    if minor_planet is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    observation = observing_session.find_observation_by_minor_planet_id(minor_planet.id)

    if observation is not None:
        db.session.delete(observation)
        db.session.commit()

    flash('Observation log deleted.', 'form-success')
    return redirect(url_for('main_minor_planet.minor_planet_observation_log', minor_planet_id=minor_planet_id, back=back, back_id=back_id))


def _do_redirect(url, minor_planet, splitview=False):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = request.args.get('fullscreen')
    splitview = 'true' if splitview else request.args.get('splitview')
    return redirect(url_for(url, minor_planet_id=minor_planet.int_designation, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed))


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
