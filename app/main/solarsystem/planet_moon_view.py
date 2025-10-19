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

from app import db

from .planet_forms import (
    PlanetFindChartForm,
)

from app.main.forms import ObservationLogForm

from app.models import (
    Observation,
    ObservationTargetType,
    PlanetMoon,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    common_ra_dec_dt_fsz_from_request,
)

from app.commons.utils import to_float, is_splitview_supported, is_mobile
from app.commons.observing_session_utils import find_observing_session, show_observation_log, combine_observing_session_date_time
from app.commons.observation_form_utils import assign_equipment_choices

from ... import csrf
from app.commons.coordinates import ra_to_str, dec_to_str
from app.commons.solar_system_chart_utils import AU_TO_KM, create_planet_moon_obj

utc = dt_module.timezone.utc

main_planet_moon = Blueprint('main_planet_moon', __name__)


class PlanetMoonData:
    def __init__(self, ra, dec, mag, distance):
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


@main_planet_moon.route('/planet-moons', methods=['GET', 'POST'])
def planet_moons():
    pl_moons = PlanetMoon.get_all()
    return render_template('main/solarsystem/planet_moons.html', planet_moons_enumerate=enumerate(pl_moons))


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/seltab')
def planet_moon_seltab(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    seltab = request.args.get('seltab', None)

    if not seltab and request.args.get('embed'):
        seltab = session.get('planet_moon_embed_seltab', None)

    if seltab == 'catalogue_data':
        return _do_redirect('main_planet_moon.planet_moon_catalogue_data', planet_moon)

    if show_observation_log():
        return _do_redirect('main_planet_moon.planet_moon_observation_log', planet_moon)

    if request.args.get('embed'):
        return _do_redirect('main_planet_moon.planet_moon_catalogue_data', planet_moon)

    kwargs = {}
    if is_splitview_supported():
        kwargs['fullscreen' if is_mobile() else 'splitview'] = True

    return _do_redirect('main_planet_moon.planet_moon_info', planet_moon, **kwargs)


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>', methods=['GET', 'POST'])
@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/info', methods=['GET', 'POST'])
@csrf.exempt
def planet_moon_info(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_moon_embed_seltab'] = 'info'

    form = PlanetFindChartForm()

    plm_obj = create_planet_moon_obj(planet_moon.name)

    common_ra_dec_dt_fsz_from_request(form, plm_obj.ra, plm_obj.dec, 60)

    chart_control = common_prepare_chart_data(form)

    show_obs_log = show_observation_log()

    default_chart_iframe_url = url_for('main_planet_moon.planet_moon_catalogue_data',
                                       back=request.args.get('back'), back_id=request.args.get('back_id'),
                                       planet_moon_name=planet_moon_name, embed='planet_moons', allow_back='false')

    return render_template('main/solarsystem/planet_moon_info.html', fchart_form=form, type='info',
                           planet_moon=planet_moon, plm_ra=plm_obj.ra, plm_dec=plm_obj.dec, chart_control=chart_control,
                           show_obs_log=show_obs_log, embed=embed, default_chart_iframe_url=default_chart_iframe_url)


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/chart-pos-img', methods=['GET'])
def planet_moon_chart_pos_img(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    plm_ra = to_float(request.args.get('obj_ra'), None)
    plm_dec = to_float(request.args.get('obj_dec'), None)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(plm_ra, plm_dec, visible_objects=visible_objects,)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/chart-pdf', methods=['GET'])
def planet_moon_chart_pdf(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    img_bytes = common_chart_pdf_img(None, None)

    return send_file(img_bytes, mimetype='application/pdf')


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/catalogue-data')
def planet_moon_catalogue_data(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_moon_embed_seltab'] = 'catalogue_data'

    show_obs_log = show_observation_log()

    plm_obj = create_planet_moon_obj(planet_moon.name)

    planet_moon_data = PlanetMoonData(plm_obj.ra, plm_obj.dec, plm_obj.mag, plm_obj.distance)

    return render_template('main/solarsystem/planet_moon_info.html', type='catalogue_data', planet_moon=planet_moon,
                           planet_moon_data=planet_moon_data, show_obs_log=show_obs_log, embed=embed)


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/observation-log', methods=['GET', 'POST'])
def planet_moon_observation_log(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    embed = request.args.get('embed')
    if embed:
        session['planet_moon_embed_seltab'] = 'info'

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    form = ObservationLogForm()
    assign_equipment_choices(form)
    observation = observing_session.find_observation_by_planet_moon_id(planet_moon.id)
    is_new_observation_log = observation is None

    if is_new_observation_log:
        date_from = datetime.now()
        if date_from.date() != observing_session.date_from.date() and date_from.date() != observing_session.date_to.date():
            date_from = observing_session.date_from
        observation = Observation(
            observing_session_id=observing_session.id,
            target_type=ObservationTargetType.PLANET_MOON,
            planet_moon_id=planet_moon.id,
            date_from=date_from,
            date_to=date_from,
            notes=form.notes.data if form.notes.data else '',
            telescope_id=form.telescope.data if form.telescope.data != -1 else None,
            eyepiece_id=form.eyepiece.data if form.eyepiece.data != -1 else None,
            filter=form.filter.data if form.filter.data != -1 else None,
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
            return redirect(url_for('main_planet_moon.planet_moon_observation_log', planet_moon_name=planet_moon_name,
                                    back=back, back_id=back_id, embed=request.args.get('embed')))
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
        session['planet_moon_embed_seltab'] = 'obs_log'

    return render_template('main/solarsystem/planet_moon_info.html', type='observation_log', planet_moon=planet_moon, form=form,
                           embed=embed, is_new_observation_log=is_new_observation_log, observing_session=observing_session,
                           back=back, back_id=back_id, has_observations=False, show_obs_log=True,
                           )


@main_planet_moon.route('/planet-moon/<string:planet_moon_name>/observation-log-delete', methods=['GET', 'POST'])
def planet_moon_observation_log_delete(planet_moon_name):
    planet_moon = PlanetMoon.get_by_name(planet_moon_name)
    if planet_moon is None:
        abort(404)

    back = request.args.get('back')
    back_id = request.args.get('back_id')
    observing_session = find_observing_session(back, back_id)

    observation = observing_session.find_observation_by_planet_moon_id(planet_moon.id)

    if observation is not None:
        db.session.delete(observation)
        db.session.commit()

    flash('Observation log deleted.', 'form-success')
    return redirect(url_for('main_planet_moon.planet_moon_observation_log', planet_moon_name=planet_moon_name, back=back, back_id=back_id))


def _do_redirect(url, planet_moon, splitview=False, fullscreen=False):
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    embed = request.args.get('embed', None)
    fullscreen = 'true' if fullscreen else request.args.get('fullscreen')
    splitview = 'true' if splitview else request.args.get('splitview')
    return redirect(url_for(url, planet_moon_name=planet_moon.name, back=back, back_id=back_id, fullscreen=fullscreen, splitview=splitview, embed=embed))


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
