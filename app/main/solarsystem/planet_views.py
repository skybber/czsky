import json
import base64

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

from .planet_forms import (
    PlanetFindChartForm,
    PlanetObservationLogForm,
)

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
    common_ra_dec_fsz_from_request,
)

from app.commons.utils import to_float
from app.commons.observing_session_utils import find_observing_session, show_observation_log

from ... import csrf

utc = dt_module.timezone.utc

main_planet = Blueprint('main_planet', __name__)


@main_planet.route('/planets', methods=['GET', 'POST'])
def planets():
    planets = Planet.get_all()
    return render_template('main/solarsystem/planets.html', planets_enumerate=enumerate(planets))


@main_planet.route('/planet/<string:planet_iau_code>', methods=['GET', 'POST'])
@main_planet.route('/planet/<string:planet_iau_code>/info', methods=['GET', 'POST'])
@csrf.exempt
def planet_info(planet_iau_code):
    """View a planet info."""
    planet =Planet.get_by_iau_code(planet_iau_code)
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
        trajectory_b64 = get_trajectory_b64(d1, d2, ts, earth, planet.eph)

    planet_ra_ang, planet_dec_ang, distance = earth.at(t).observe(planet.eph).radec()
    planet_ra = planet_ra_ang.radians
    planet_dec = planet_dec_ang.radians

    if not common_ra_dec_fsz_from_request(form):
        if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
            form.ra.data = planet_ra
            form.dec.data = planet_dec

    chart_control = common_prepare_chart_data(form)

    show_obs_log = show_observation_log()

    return render_template('main/solarsystem/planet_info.html', fchart_form=form, type='info', planet=planet,
                           planet_ra=planet_ra, planet_dec=planet_dec, chart_control=chart_control, trajectory=trajectory_b64,
                           show_obs_log=show_obs_log,)


@main_planet.route('/planet/<string:planet_iau_code>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_pos_img(planet_iau_code, ra, dec):
    planet =Planet.get_by_iau_code(planet_iau_code)
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


@main_planet.route('/planet/<string:planet_iau_code>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_legend_img(planet_iau_code, ra, dec):
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    planet_ra = to_float(request.args.get('obj_ra'), None)
    planet_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_legend_img(planet_ra, planet_dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_planet.route('/planet/<string:planet_iau_code>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def planet_chart_pdf(planet_iau_code, ra, dec):
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

    img_bytes = common_chart_pdf_img(None, None, ra, dec, trajectory=trajectory)

    return send_file(img_bytes, mimetype='application/pdf')


@main_planet.route('/planet/<string:planet_iau_code>')
@main_planet.route('/planet/<string:planet_iau_code>/catalogue_data')
def planet_catalogue_data(planet_iau_code):
    """View a planet catalog info."""
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)
    return render_template('main/solarsystem/planet_info.html', type='catalogue_data')

@main_planet.route('/planet/<string:planet_iau_code>/observation-log', methods=['GET', 'POST'])
def planet_observation_log(planet_iau_code):
    planet = Planet.get_by_iau_code(planet_iau_code)
    if planet is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    form = PlanetObservationLogForm()
    observation = observing_session.find_observation_by_planet_id(planet.id)
    is_new_observation_log = observation is None

    if is_new_observation_log:
        now = datetime.now()
        observation = Observation(
            observing_session_id=observing_session.id,
            target_type=ObservationTargetType.PLANET,
            planet_id=planet.id,
            date_from=now,
            date_to=now,
            notes=form.notes.data if form.notes.data else '',
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )

    if request.method == 'POST':
        if form.validate_on_submit():
            observation.notes = form.notes.data
            observation.update_by = current_user.id
            observation.update_date = datetime.now()
            db.session.add(observation)
            db.session.commit()
            flash('Observation log successfully updated', 'form-success')
            return redirect(url_for('main_planet.planet_observation_log', planet_iau_code=planet_iau_code, back=back, back_id=back_id, embed=request.args.get('embed')))
    else:
        form.notes.data = observation.notes

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
def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
