import json
import base64
import math

from datetime import date, datetime, timedelta
import datetime as dt_module

from flask import (
    abort,
    Blueprint,
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

from app import db
import fchart3

from .planet_forms import (
    PlanetFindChartForm,
)

from app.main.forms import ObservationLogForm

from app.models import (
    Observation,
    ObservationTargetType,
    Planet,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    get_trajectory_b64,
    common_ra_dec_dt_fsz_from_request,
)

from app.commons.utils import to_float, is_splitview_supported, is_mobile
from app.commons.observing_session_utils import find_observing_session, show_observation_log, combine_observing_session_date_time
from app.commons.observation_form_utils import assign_equipment_choices

from ... import csrf
from app.commons.coordinates import ra_to_str, dec_to_str
from app.commons.solar_system_chart_utils import (
    AU_TO_KM,
    create_solar_system_body_obj,
    get_planet_orbital_period,
    get_planet_synodic_period,
    YEAR_DAYS
)

utc = dt_module.timezone.utc

main_planet = Blueprint('main_planet', __name__)


class PlanetData:
    def __init__(self, orbit_period, ra, dec, mag, angular_diameter, phase, distance, orbital_period, synodic_period):
        self.orbit_period = orbit_period
        self.ra = ra
        self.dec = dec
        self.mag = mag
        self.angular_diameter = angular_diameter
        self.phase = phase
        self.distance_au = distance / AU_TO_KM
        self.distance = distance
        self.orbital_period = orbital_period
        self.orbital_period_year = orbital_period / YEAR_DAYS
        self.synodic_period = synodic_period
        self.synodic_period_year = synodic_period / YEAR_DAYS

    def ra_str(self):
        return ra_to_str(self.ra)

    def dec_str(self):
        return dec_to_str(self.dec)

    def angular_diameter_seconds(self):
        return self.angular_diameter * 180.0 * 60 * 60 / math.pi


@main_planet.route('/planets', methods=['GET', 'POST'])
def planets():
    planets = Planet.get_all()
    return render_template('main/solarsystem/planets.html', planets_enumerate=enumerate(planets))


@main_planet.route('/planet/<string:planet_iau_code>/seltab')
def planet_seltab(planet_iau_code):
    """View a planet seltab."""
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    seltab = request.args.get('seltab', None)

    if not seltab and request.args.get('embed'):
        seltab = session.get('planet_embed_seltab', None)

    if seltab == 'catalogue_data':
        return _do_redirect('main_planet.planet_catalogue_data', planet)

    if seltab == 'visibility':
        return _do_redirect('main_planet.planet_visibility', planet)

    if show_observation_log():
        return _do_redirect('main_planet.planet_observation_log', planet)

    if request.args.get('embed'):
        return _do_redirect('main_planet.planet_catalogue_data', planet)

    kwargs = {}
    if is_splitview_supported():
        kwargs['fullscreen' if is_mobile() else 'splitview'] = True

    return _do_redirect('main_planet.planet_info', planet, **kwargs)


@main_planet.route('/planet/<string:planet_iau_code>', methods=['GET', 'POST'])
@main_planet.route('/planet/<string:planet_iau_code>/info', methods=['GET', 'POST'])
@csrf.exempt
def planet_info(planet_iau_code):
    """View a planet info."""
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_embed_seltab'] = 'info'

    form = PlanetFindChartForm()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']

    if not form.date_from.data or not form.date_to.data:
        today = datetime.today()
        form.date_from.data = today
        form.date_to.data = today + timedelta(days=7)

    t = ts.now()
    # trajectory_b64 = None
    # if (form.date_from.data is not None) and (form.date_to.data is not None) and form.date_from.data < form.date_to.data:
    #     d1 = datetime(form.date_from.data.year, form.date_from.data.month, form.date_from.data.day)
    #     d2 = datetime(form.date_to.data.year, form.date_to.data.month, form.date_to.data.day)
    #     today = date.today()
    #     if today < d1.date():
    #         t = ts.from_datetime(d1.replace(tzinfo=utc))
    #     elif today > d2.date():
    #         t = ts.from_datetime(d2.replace(tzinfo=utc))
    #     trajectory_b64 = get_trajectory_b64(d1, d2, ts, earth, planet.eph)

    planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    planet_ra = planet_ra_ang.radians
    planet_dec = planet_dec_ang.radians

    common_ra_dec_dt_fsz_from_request(form, planet_ra, planet_dec, 60)

    chart_control = common_prepare_chart_data(form)

    show_obs_log = show_observation_log()

    default_chart_iframe_url = url_for('main_planet.planet_catalogue_data', planet_iau_code=planet_iau_code,
                                       back=request.args.get('back'), back_id=request.args.get('back_id'),
                                       embed='planets', allow_back='false')

    return render_template('main/solarsystem/planet_info.html', fchart_form=form, type='info', planet=planet,
                           planet_ra=planet_ra, planet_dec=planet_dec, chart_control=chart_control, trajectory=None,
                           show_obs_log=show_obs_log, embed=embed, default_chart_iframe_url=default_chart_iframe_url)


@main_planet.route('/planet/<string:planet_iau_code>/chart-pos-img', methods=['GET'])
def planet_chart_pos_img(planet_iau_code):
    planet = Planet.get_by_iau_code(planet_iau_code)
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

    img_bytes, img_format = common_chart_pos_img(planet_ra, planet_dec, visible_objects=visible_objects,
                                                 trajectory=trajectory)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_planet.route('/planet/<string:planet_iau_code>/chart-pdf', methods=['GET'])
def planet_chart_pdf(planet_iau_code):
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    # planet_ra = to_float(request.args.get('obj_ra'), None)
    # planet_dec = to_float(request.args.get('obj_dec'), None)

    trajectory_b64 = request.args.get('trajectory')
    if trajectory_b64:
        trajectory_json = base64.b64decode(trajectory_b64)
        trajectory = json.loads(trajectory_json)
    else:
        trajectory = None

    img_bytes = common_chart_pdf_img(None, None, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_planet.route('/planet/<string:planet_iau_code>/catalogue-data')
def planet_catalogue_data(planet_iau_code):
    """View a planet catalogue data."""
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_embed_seltab'] = 'catalogue_data'

    show_obs_log = show_observation_log()

    body_enum = fchart3.SolarSystemBody.get_by_name(planet.iau_code)
    sb = create_solar_system_body_obj(load('de421.bsp'), body_enum, load.timescale(builtin=True).now())

    phase = (1 + math.cos(sb.phase)) / 2

    planet_data = PlanetData(1000, sb.ra, sb.dec, sb.mag, sb.angular_radius*2, phase,
                             sb.distance, get_planet_orbital_period(planet_iau_code),
                             get_planet_synodic_period(planet_iau_code))

    return render_template('main/solarsystem/planet_info.html', type='catalogue_data', planet=planet,
                           planet_data=planet_data, show_obs_log=show_obs_log, embed=embed)


@main_planet.route('/planet/<string:planet_iau_code>/visibility', methods=['GET', 'POST'])
def planet_visibility(planet_iau_code):
    """View visibility chart for a planet."""
    from app.commons.chart_generator import resolve_chart_city_lat_lon, get_chart_datetime

    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    embed = request.args.get('embed', None)
    if embed:
        session['planet_embed_seltab'] = 'visibility'

    # Calculate current planet position
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    earth = eph['earth']
    t = ts.now()

    planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    planet_ra = planet_ra_ang.radians
    planet_dec = planet_dec_ang.radians

    # Resolve location and prepare visibility parameters
    city_name, lat, lon = resolve_chart_city_lat_lon()
    chart_theme = session.get('theme', 'dark')
    chart_date = get_chart_datetime().strftime('%Y-%m-%d')

    show_obs_log = show_observation_log()

    return render_template('main/solarsystem/planet_info.html', type='visibility', planet=planet,
                           embed=embed, show_obs_log=show_obs_log,
                           location_city_name=city_name, location_lat=lat, location_lon=lon,
                           chart_theme=chart_theme, chart_date=chart_date,
                           planet_ra=planet_ra, planet_dec=planet_dec,
                           )


@main_planet.route('/planet/<string:planet_iau_code>/observation-log', methods=['GET', 'POST'])
def planet_observation_log(planet_iau_code):
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_embed_seltab'] = 'info'

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    form = ObservationLogForm()
    assign_equipment_choices(form)
    observation = observing_session.find_observation_by_planet_id(planet.id)
    is_new_observation_log = observation is None

    if is_new_observation_log:
        date_from = datetime.now()
        if date_from.date() != observing_session.date_from.date() and date_from.date() != observing_session.date_to.date():
            date_from = observing_session.date_from
        observation = Observation(
            observing_session_id=observing_session.id,
            target_type=ObservationTargetType.PLANET,
            planet_id=planet.id,
            date_from=date_from,
            date_to=date_from,
            notes=form.notes.data if form.notes.data else '',
            telescope_id = form.telescope.data if form.telescope.data != -1 else None,
            eyepiece_id = form.eyepiece.data if form.eyepiece.data != -1 else None,
            filter = form.filter.data if form.filter.data != -1 else None,
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
            observation.filter_id = form.filter.data if form.filter.data != -1 else None
            observation.date_from = combine_observing_session_date_time(observing_session, form.date_from.data, form.time_from.data)
            observation.update_by = current_user.id
            observation.update_date = datetime.now()
            db.session.add(observation)
            db.session.commit()
            flash('Observation log successfully updated', 'form-success')
            return redirect(url_for('main_planet.planet_observation_log', planet_iau_code=planet_iau_code, back=back, back_id=back_id, embed=request.args.get('embed')))
    else:
        form.notes.data = observation.notes
        if observation.telescope_id:
            form.telescope.data = observation.telescope_id
        elif observing_session.default_telescope_id is not None:
            form.telescope.data = observing_session.default_telescope_id
        else:
            form.telescope.data = -1
        form.eyepiece.data = observation.eyepiece_id if observation.eyepiece_id is not None else -1
        form.filter.data = observation.filter_id if observation.filter_id is not None else -1
        form.date_from.data = observation.date_from
        form.time_from.data = observation.date_from

    embed = request.args.get('embed')
    if embed:
        session['planet_embed_seltab'] = 'obs_log'

    return render_template('main/solarsystem/planet_info.html', type='observation_log', planet=planet, form=form,
                           embed=embed, is_new_observation_log=is_new_observation_log, observing_session=observing_session,
                           back=back, back_id=back_id, has_observations=False, show_obs_log=True,
                           )


@main_planet.route('/planet/<string:planet_iau_code>/observation-log-delete', methods=['GET', 'POST'])
def planet_observation_log_delete(planet_iau_code):
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    observation = observing_session.find_observation_by_planet_id(planet.id)

    if observation is not None:
        db.session.delete(observation)
        db.session.commit()

    flash('Observation log deleted.', 'form-success')
    return redirect(url_for('main_planet.planet_observation_log', planet_iau_code=planet_iau_code, back=back, back_id=back_id))


def _do_redirect(url, planet, splitview=False, fullscreen=False):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = 'true' if fullscreen else request.args.get('fullscreen')
    splitview = 'true' if splitview else request.args.get('splitview')
    dt = request.args.get('dt')
    return redirect(url_for(url, planet_iau_code=planet.iau_code, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed, dt=dt))


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
