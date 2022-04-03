import os
from datetime import datetime
from io import StringIO, BytesIO
import base64
import codecs

from werkzeug.utils import secure_filename

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
from flask_babel import gettext

from app import db

from .observing_session_forms import (
    ObservingSessionNewForm,
    ObservingSessionEditForm,
    ObservingSessionItemsEditForm,
    ObservingSessionExportForm,
    ObservationSessionRunPlanForm,
)

from app.models import (
    DeepskyObject,
    ImportHistoryRec,
    ImportHistoryRecStatus,
    ImportType,
    Location,
    Observation,
    ObservingSession,
    ObsSessionPlanRun,
    Seeing,
    SessionPlan,
    Transparency,
)

from app.commons.search_utils import get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter
from app.commons.dso_utils import normalize_dso_name
from .observing_session_export import create_oal_observations
from .observing_session_import import import_observations

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
    common_set_initial_ra_dec,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.coordinates import *

main_observing_session = Blueprint('main_observing_session', __name__)


@main_observing_session.route('/observing-sessions', methods=['GET', 'POST'])
@login_required
def observing_sessions():
    """View observing sessions."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observing_sessions = ObservingSession.query.filter_by(user_id=current_user.id).order_by(ObservingSession.date_from.desc())
    search = False

    obs_sessions_for_render = observing_sessions.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=observing_sessions.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observing_sessions.html', observing_sessions=obs_sessions_for_render, pagination=pagination)


def _check_observing_session(observing_session, allow_public=False):
    if observing_session is None:
        abort(404)
    if current_user.is_anonymous:
        if observing_session.is_public:
            return False
        abort(404)
    elif observing_session.user_id != current_user.id:
        if allow_public and observing_session.is_public:
            return False
        abort(404)

    return True


@main_observing_session.route('/observing-session/<int:observing_session_id>', methods=['GET'])
@main_observing_session.route('/observing-session/<int:observing_session_id>/info', methods=['GET'])
def observing_session_info(observing_session_id):
    """View a observation info."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)
    location_position_mapy_cz_url = None
    location_position_google_maps_url = None
    if not observing_session.location_id and observing_session.location_position:
        lat, lon = parse_latlon(observing_session.location_position)
        location_position_mapy_cz_url = mapy_cz_url(lon, lat)
        location_position_google_maps_url = google_url(lon, lat)

    return render_template('main/observation/observing_session_info.html', observing_session=observing_session, type='info', is_mine_observing_session=is_mine_observing_session,
                           location_position_mapy_cz_url=location_position_mapy_cz_url, location_position_google_maps_url=location_position_google_maps_url)


@main_observing_session.route('/new-observing_session', methods=['GET', 'POST'])
@login_required
def new_observing_session():
    """Create new observing_session"""
    form = ObservingSessionNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        location_position = None
        location_id = None
        if isinstance(form.location.data, int) or form.location.data.isdigit():
            location_id = int(form.location.data)
        else:
            location_position = form.location.data

        observing_session = ObservingSession(
            user_id=current_user.id,
            title=form.title.data,
            date_from=form.date_from.data,
            date_to=form.date_to.data,
            location_id=location_id,
            location_position=location_position,
            sqm=form.sqm.data,
            faintest_star=form.faintest_star.data,
            seeing=form.seeing.data,
            transparency=form.transparency.data,
            rating=form.rating.data,
            weather=form.weather.data,
            equipment=form.equipment.data,
            notes=form.notes.data,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )

        db.session.add(observing_session)
        db.session.commit()
        flash(gettext('Observing session successfully created'), 'form-success')
        return redirect(url_for('main_observing_session.observing_session_edit', observing_session_id=observing_session.id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observing_session_edit.html', form=form, is_new=True, location=location, location_position=location_position)


@main_observing_session.route('/observing-session/<int:observing_session_id>/edit', methods=['GET', 'POST'])
@login_required
def observing_session_edit(observing_session_id):
    """Update observing_session"""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)

    form = ObservingSessionEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            location_position = None
            location_id = None
            if isinstance(form.location.data, int) or form.location.data.isdigit():
                location_id = int(form.location.data)
            else:
                location_position = form.location.data

            observing_session.user_id = current_user.id
            observing_session.title = form.title.data
            observing_session.date_from = form.date_from.data
            observing_session.date_to = form.date_to.data
            observing_session.location_id = location_id
            observing_session.location_position = location_position
            observing_session.sqm = form.sqm.data
            observing_session.faintest_star = form.faintest_star.data
            observing_session.seeing = form.seeing.data
            observing_session.transparency = form.transparency.data
            observing_session.rating = int(form.rating.data) * 2
            observing_session.weather = form.weather.data
            observing_session.equipment = form.equipment.data
            observing_session.notes = form.notes.data
            observing_session.update_by = current_user.id
            observing_session.update_date = datetime.now()
            observing_session.is_public = form.is_public.data

            db.session.add(observing_session)
            db.session.commit()

            flash(gettext('Observing session successfully updated'), 'form-success')

            if form.goback.data == 'true':
                return redirect(url_for('main_observing_session.observing_session_info', observing_session_id=observing_session.id))
            return redirect(url_for('main_observing_session.observing_session_edit', observing_session_id=observing_session.id))
    else:
        form.title.data = observing_session.title
        form.date_from.data = observing_session.date_from
        form.date_to.data = observing_session.date_to
        form.location.data = observing_session.location_id if observing_session.location_id is not None else observing_session.location_position
        form.sqm.data = observing_session.sqm
        form.faintest_star.data = observing_session.faintest_star
        form.seeing.data = observing_session.seeing if observing_session.seeing else Seeing.AVERAGE
        form.transparency.data = observing_session.transparency if observing_session.transparency else Transparency.AVERAGE
        form.rating.data = observing_session.rating // 2 if observing_session.rating is not None else 0
        form.weather.data = observing_session.weather
        form.equipment.data = observing_session.equipment
        form.notes.data = observing_session.notes
        form.is_public.data = observing_session.is_public

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observing_session_edit.html', form=form, is_new=False, observing_session=observing_session,
                           location=location, location_position=location_position)


@main_observing_session.route('/observing-session/<int:observing_session_id>/items-edit', methods=['GET', 'POST'])
@login_required
def observing_session_items_edit(observing_session_id):
    """Update observing_session items"""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)

    form = ObservingSessionItemsEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            for observation in observing_session.observations:
                observation.deepsky_objects = []
                db.session.delete(observation)
            observing_session.observations.clear()
            for item_form in form.items[1:]:
                item_time = datetime.combine(observing_session.date_from, item_form.date_from.data)
                dsos, notes = _parse_compound_notes(item_form.comp_notes.data)
                observation = Observation(
                    observing_session_id=observing_session.id,
                    user=current_user.id,
                    date_from=item_time,
                    date_to=item_time,
                    notes=notes,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                )
                observing_session.observations.append(observation)

                for dso_name in dsos:
                    dso_name = normalize_dso_name(dso_name)
                    dso = DeepskyObject.query.filter_by(name=dso_name).first()
                    if dso:
                        observation.deepsky_objects.append(dso)
                    else:
                        flash(gettext('Deepsky object \'{}\' not found').format(dso_name), 'form-warning')

            db.session.add(observing_session)
            db.session.commit()

            if form.goback.data == 'true':
                return redirect(url_for('main_observing_session.observing_session_info', observing_session_id=observing_session.id))
            return redirect(url_for('main_observing_session.observing_session_items_edit', observing_session_id=observing_session.id))
    else:
        for oi in observing_session.observations:
            oif = form.items.append_entry()
            comp_dsos = ','.join([dso.name for dso in oi.deepsky_objects])
            if comp_dsos:
                comp_dsos += ':'
            oif.comp_notes.data = comp_dsos + oi.notes
            oif.date_from.data = oi.date_from

    return render_template('main/observation/observing_session_items_edit.html', form=form, observing_session=observing_session)


def _parse_compound_notes(comp_notes):
    if ':' in comp_notes:
        comp_dso, notes = comp_notes.split(':', 1)
        return comp_dso.split(','), notes
    else:
        return (), comp_notes


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


@main_observing_session.route('/observing-session/<int:observing_session_id>/delete')
@login_required
def observing_session_delete(observing_session_id):
    """Request deletion of a observing_session."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)
    db.session.delete(observing_session)
    db.session.commit()
    flash(gettext('Observation was deleted'), 'form-success')
    return redirect(url_for('main_observing_session.observing_sessions'))


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart', methods=['GET', 'POST'])
def observing_session_chart(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    form = ChartForm()

    dso_id = request.args.get('dso_id')
    observing_session_item = None
    dso = None

    idso_id = int(dso_id) if dso_id and dso_id.isdigit() else None
    for oitem in observing_session.observations:
        for oitem_dso in oitem.deepsky_objects:
            if idso_id is None or oitem_dso.id == idso_id:
                observing_session_item = oitem
                dso = oitem_dso
                break
        if observing_session_item is not None:
            break

    if not common_ra_dec_fsz_from_request(form):
        if observing_session_item:
            if form.ra.data is None or form.dec.data is None:
                if not dso:
                    dso = observing_session_item.deepsky_objects[0] if observing_session_item and observing_session_item.deepsky_objects else None
                form.ra.data = dso.ra if dso else 0
                form.dec.data = dso.dec if dso else 0
        else:
            common_set_initial_ra_dec(form)

    if observing_session_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='observing_session', back_id=observing_session.id, dso_id=dso.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    chart_control = common_prepare_chart_data(form)

    return render_template('main/observation/observing_session_info.html', fchart_form=form, type='chart', observing_session=observing_session, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_observing_session=is_mine_observing_session)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def observing_session_chart_pos_img(observing_session_id, ra, dec):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    highlights_dso_list = []

    for observation in observing_session.observations:
        highlights_dso_list.extend(observation.deepsky_objects)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def observing_session_chart_legend_img(observing_session_id, ra, dec):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_observing_session.route('/observing-session/<int:observing_session_id>/run-plan', methods=['GET', 'POST'])
def observing_session_run_plan(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, False)
    if not is_mine_observing_session:
        abort(404)

    form = ObservationSessionRunPlanForm()

    session_plan_id = None
    if request.method == 'POST':
        if form.validate_on_submit():
            session_plan_id = form.session_plan.data
    else:
        session_plan_id = form.session_plan.data
        if session_plan_id is None:
            running_plan_id = session.get('running_plan_id', None)
            if running_plan_id is not None:
                observing_session_plan_run = ObsSessionPlanRun.query.filter_by(id=int(running_plan_id)).first()
                if observing_session_plan_run and \
                        not observing_session_plan_run.session_plan.is_archived and \
                        observing_session_plan_run.session_plan.user_id == current_user.id:
                    session_plan_id = observing_session_plan_run.session_plan.id
                else:
                    session.pop('running_plan_id')

    available_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False) \
        .order_by(SessionPlan.for_date.desc())

    observing_session_plan_run = None

    observed_items = []
    not_observed_plan_items = []

    session_plan = None

    if session_plan_id is not None:
        session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
        if session_plan.user_id == current_user.id:
            observing_session_plan_run = ObsSessionPlanRun.query.filter_by(observing_session_id=observing_session_id, session_plan_id=session_plan_id) \
                                                     .first()
            form.session_plan.data = session_plan_id
        else:
            session.pop('running_plan_id')
            form.session_plan.data = None

    if session_plan:
        for plan_item in session_plan.session_plan_items:
            observed = False
            for observation in observing_session.observations:
                for dso in observation.deepsky_objects:
                    if dso.id == plan_item.dso_id:
                        observed_items.append((plan_item, observation))
                        observed = True
                        break
                if observed:
                    break
            if not observed:
                not_observed_plan_items.append(plan_item)

    return render_template('main/observation/observing_session_info.html', observing_session=observing_session, type='run_plan',
                           run_plan_form=form, is_mine_observing_session=True, available_session_plans=available_session_plans,
                           observed_items=observed_items, not_observed_plan_items=not_observed_plan_items,
                           observing_session_plan_run=observing_session_plan_run)


@main_observing_session.route('/observing-session/<int:observing_session_plan_run_id>/run-plan-redirect', methods=['GET'])
def observing_session_run_plan_redirect(observing_session_plan_run_id):
    observing_session_plan_run = ObsSessionPlanRun.query.filter_by(id=observing_session_plan_run_id).first()
    if not observing_session_plan_run:
        abort(404)
    return redirect(url_for('main_observing_session.observing_session_run_plan', observing_session_id=observing_session_plan_run.observing_session_id))


@main_observing_session.route('/observing-session/<int:observing_session_id>/<int:session_plan_id>/run-plan-execute', methods=['GET'])
def observing_session_run_plan_execute(observing_session_id, session_plan_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, False)
    if not is_mine_observing_session:
        abort(404)
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None or session_plan.user_id != current_user.id:
        abort(404)

    observing_session_plan_run = ObsSessionPlanRun.query.filter_by(observing_session_id=observing_session_id, session_plan_id=session_plan_id) \
        .first()

    if observing_session_plan_run is None:
        observing_session_plan_run = ObsSessionPlanRun(
            observing_session_id=observing_session_id,
            session_plan_id=session_plan_id
        )
        db.session.add(observing_session_plan_run)
        db.session.commit()

    session['running_plan_id'] = observing_session_plan_run.id

    if len(session_plan.session_plan_items) and session_plan.session_plan_items[0].deepskyObject is not None:
        dso_name = session_plan.session_plan_items[0].deepskyObject.name
    else:
        dso_name = 'M1'  # fallback
    return redirect(url_for('main_deepskyobject.deepskyobject_observation_log', dso_id=dso_name, back='running_plan', back_id=observing_session_plan_run.id))


@main_observing_session.route('/observing-sessions-export', methods=['GET', 'POST'])
@login_required
def observing_sessions_export():
    """Export observing sessions."""
    form = ObservingSessionExportForm()
    if request.method == 'POST':
        buf = StringIO()
        buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
        observing_sessions = ObservingSession.query.filter_by(user_id=current_user.id).all()
        oal_observations = create_oal_observations(current_user, observing_sessions)
        oal_observations.export(buf, 0)
        mem = BytesIO()
        mem.write(codecs.BOM_UTF8)
        mem.write(buf.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(mem, as_attachment=True,
                         attachment_filename='observing_sessions-' + current_user.user_name + '.xml',
                         mimetype='text/xml')
    return render_template('main/observation/observing_sessions_export.html', about_oal=_get_about_oal())


@main_observing_session.route('/observing-sessions-import', methods=['GET', 'POST'])
@login_required
def observing_sessions_import():
    return render_template('main/observation/observing_sessions_import.html', about_oal=_get_about_oal(), log_warn=[], log_error=[])


@main_observing_session.route('/observing-sessions-import-upload', methods=['GET', 'POST'])
@login_required
def observing_sessions_import_upload():
    if 'file' not in request.files:
        flash(gettext('No file part'), 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash(gettext('No selected file'))
        return redirect(request.url)
    log_warn, log_error = [], []
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        import_history_rec = ImportHistoryRec()
        import_history_rec.import_type = ImportType.OBSERVATION
        import_history_rec.status = ImportHistoryRecStatus.IMPORTED
        import_history_rec.create_by = current_user.id
        import_history_rec.create_date = datetime.now()
        db.session.add(import_history_rec)
        db.session.commit()

        encoding = None

        with open(path, 'r', errors='replace') as f:
            firstline = f.readline().rstrip()
            if firstline:
                m = re.search('encoding="(.*)"', firstline)
                if m:
                    encoding = m.group(1).lower()

        if encoding:
            with codecs.open(path, 'r', encoding=encoding) as oal_file:
                log_warn, log_error = oal_observations = import_observations(current_user, current_user, import_history_rec.id, oal_file)
                print(log_warn, flush=True)
                print(log_error, flush=True)
        else:
            with open(path) as oal_file:
                log_warn, log_error = oal_observations = import_observations(current_user, current_user, import_history_rec.id, oal_file)

        if log_warn is not None and log_error is not None:
            log = 'Warnings:\n' + '\n'.join(log_warn) + '\nErrrors:' + '\n'.join(log_error)
            import_history_rec.log = log
            import_history_rec.create_date = datetime.now()
            db.session.add(import_history_rec)
            db.session.commit()
        else:
            db.session.delete(import_history_rec)
            db.session.commit()
        flash(gettext('Observations imported.'), 'form-success')

    return render_template('main/observation/observing_sessions_import.html', about_oal=_get_about_oal(), log_warn=log_warn, log_error=log_error)


def _get_about_oal():
    return gettext("""
## Goal
**OpenAstronomyLog** is a free and open XML schema definition for all kinds of astronomical observations. 
Software that supports this schema enables an observer to share observations with other observers or move observations 
among software products.

## History
The schema (formerly known as COMAST schema) was primarily developed by the 
german ["Fachgruppe für Computerastronomie"](http://www.vds-astro.de/fachgruppen/computerastronomie.html) (section for computerastronomy) which is a subsection of Germany's largest
astronomy union, [VDS](http://www.vds-astro.de/) (Vereinigung der Sternfreunde e.V.) 
Starting with version 2.0 the schema was renamed from COMAST (abbr. for *Com*puter *Ast*ronomy) to **OpenAstronomyLog**, or **\<OAL\>**.

## Documentation
Please see our [wiki section](https://github.com/openastronomylog/openastronomylog/wiki) as well as the [doc](https://github.com/openastronomylog/openastronomylog/tree/master/doc) folder

## License
The schema is released under the [APACHE Software License 2.0](https://github.com/openastronomylog/openastronomylog/blob/master/LICENSE) and is currently supported in both open source and 
commercial software. Just [download the schema archive](https://github.com/openastronomylog/openastronomylog/blob/master/OAL21.zip?raw=true)!

## Contribution
In you want to contribute to **\<OAL\>** please join the [OpenAstronomyLog discussion group](https://groups.google.com/forum/#!forum/openastronomylog).
""")
