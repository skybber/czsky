import os
import csv
from io import StringIO, BytesIO
import base64

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
    url_for,
)
from flask_login import current_user, login_required

from app import db

from .observation_forms import (
    ObservationNewForm,
    ObservationEditForm,
    AddToObservedListForm,
)

from app.models import Observation, Location, ObservedList, ObservedListItem
from app.commons.search_utils import get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter
from .observation_form_utils import *
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
)

from app.main.chart.chart_forms import ChartForm

main_observation = Blueprint('main_observation', __name__)

@main_observation.route('/observation-menu', methods=['GET'])
@login_required
def observation_menu():
    return render_template('main/observation/observation_menu.html')

@main_observation.route('/observations', methods=['GET', 'POST'])
@login_required
def observations():
    """View observations."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observations = Observation.query.filter_by(user_id=current_user.id)
    search = False

    observations_for_render = observations.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=observations.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observations.html', observations=observations_for_render, pagination=pagination)

@main_observation.route('/observation/<int:observation_id>', methods=['GET'])
@main_observation.route('/observation/<int:observation_id>/info', methods=['GET'])
@login_required
def observation_info(observation_id):
    """View a observation info."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    return render_template('main/observation/observation_info.html', observation=observation, type='info')

@main_observation.route('/new-observation', methods=['GET', 'POST'])
@login_required
def new_observation():
    """Create new observation"""
    form = ObservationNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        if form.advmode.data == 'true':
            new_observation_id = create_from_advanced_form(form)
        else:
            new_observation_id = create_from_basic_form(form)
        if new_observation_id:
            return redirect(url_for('main_observation.observation_edit', observation_id=new_observation_id))

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()
    return render_template('main/observation/observation_edit.html', form=form, is_new=True, location=location)

@main_observation.route('/observation/<int:observation_id>/edit', methods=['GET', 'POST'])
@login_required
def observation_edit(observation_id):
    """Update observation"""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    form = ObservationEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if form.advmode.data == 'true':
                update_from_advanced_form(form, observation)
            else:
                update_from_basic_form(form, observation)

            if form.goback.data == 'true':
                return redirect(url_for('main_observation.observation_info', observation_id=observation.id))

    else:
        form.title.data = observation.title
        form.date.data = observation.date
        form.location_id.data = observation.location_id
        form.rating.data = observation.rating
        form.notes.data = observation.notes
        form.omd_content.data = observation.omd_content
        for oi in observation.observation_items:
            oif = form.items.append_entry()
            oif.deepsky_object_id_list.data = oi.txt_deepsky_objects
            oif.date_time.data = oi.date_time
            oif.notes.data = oi.notes

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/observation/observation_edit.html', form=form, is_new=False, observation=observation, location=location)

@main_observation.route('/observation/<int:observation_id>/delete')
@login_required
def observation_delete(observation_id):
    """Request deletion of a observation."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    db.session.delete(observation)
    db.session.commit()
    flash('Observation was deleted', 'form-success')
    return redirect(url_for('main_observation.observations'))


@main_observation.route('/observation/<int:observation_id>/chart', methods=['GET', 'POST'])
def observation_chart(observation_id):
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)

    form  = ChartForm()

    chart_control = common_prepare_chart_data(form)

    dso_id = request.args.get('dso_id')
    observation_item = None
    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        observation_item = next((x for x in observation.observation_items if x.deepskyObject.id == idso_id), None)

    if not observation_item:
        observation_item = ObservationItem.query.filter_by(observation_id=observation.id).first()

    if form.ra.data is None:
        form.ra.data = observation_item.deepskyObject.ra if observation_item else 0
    if form.dec.data is None:
        form.dec.data = observation_item.deepskyObject.dec if observation_item else 0

    if observation_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='observation', back_id=observation.id, dso_id=observation_item.deepskyObject.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    return render_template('main/observation/observation_info.html', fchart_form=form, type='chart', observation=observation, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url,)


@main_observation.route('/observation/<int:observation_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def  observation_chart_pos_img(observation_id, ra, dec):
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)

    highlights_dso_list = [ x.deepskyObject for x in observation.observation_items if observation ]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_observation.route('/observation/<int:observation_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def observation_chart_legend_img(observation_id, ra, dec):
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_observation.route('/observed-list', methods=['GET'])
@login_required
def observed_list():
    """View observed list."""
    add_form = AddToObservedListForm()
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    return render_template('main/observation/observed_list.html', observed_list=observed_list, add_form=add_form)


@main_observation.route('/observed-list-item-add', methods=['POST'])
@login_required
def observed_list_item_add():
    """Add item to observed list."""
    form = AddToObservedListForm()
    dso_name = normalize_dso_name(form.dso_name.data)
    if request.method == 'POST' and form.validate_on_submit():
        deepsky_object = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()
        if deepsky_object:
            observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
            if observed_list.append_deepsky_object(deepsky_object.id, current_user.id):
                flash('Object was added to observed list.', 'form-success')
            else:
                flash('Object is already on observed list.', 'form-info')
        else:
            flash('Deepsky object not found.', 'form-error')

    return redirect(url_for('main_observation.observed_list'))


@main_observation.route('/observed-list-item/<int:item_id>/delete')
@login_required
def observed_list_item_delete(item_id):
    """Remove item to observed list."""
    observed_list_item = ObservedListItem.query.filter_by(id=item_id).first()
    if observed_list_item is None:
        abort(404)
    if observed_list_item.observed_list.user_id != current_user.id:
        abort(404)
    db.session.delete(observed_list_item)
    db.session.commit()
    flash('Observed list item was deleted', 'form-success')
    return redirect(url_for('main_observation.observed_list'))


@main_observation.route('/observed-list-delete', methods=['GET'])
@login_required
def observed_list_delete():
    """delete observed list."""
    add_form = AddToObservedListForm()
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    ObservedListItem.query.filter_by(observed_list_id=observed_list.id).delete()
    db.session.commit()
    flash('Observed list deleted', 'form-success')
    return render_template('main/observation/observed_list.html', observed_list=observed_list, add_form=add_form)

@main_observation.route('/observed-list-upload', methods=['POST'])
@login_required
def observed_list_upload():
    if 'file' not in request.files:
        flash('No file part', 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        with open(path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['DSO_NAME'])
            observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
            existing_ids = set(item.dso_id for item in observed_list.observed_list_items)
            for row in reader:
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue
                object_name = dso_name.replace(' ', '')
                dso = DeepskyObject.query.filter_by(name=object_name).first()
                if dso and not dso.id in existing_ids:
                    new_item = ObservedListItem(
                        observed_list_id = observed_list.id,
                        dso_id = dso.id,
                        create_date = datetime.now(),
                        update_date = datetime.now(),
                        )
                    db.session.add(new_item)
                    existing_ids.add(dso.id)
        db.session.commit()
        os.remove(path)
        flash('Observed list updated.', 'form-success')

    return redirect(url_for('main_observation.observed_list'))

@main_observation.route('/observed-list-download', methods=['POST'])
@login_required
def observed_list_download():
    buf = StringIO()
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    for observed_item in observed_list.observed_list_items:
        if not observed_item.dso_id is None:
            buf.write(observed_item.deepskyObject.name + '\n')
    mem = BytesIO()
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, as_attachment=True,
                     attachment_filename='observed-' + current_user.user_name + '.csv',
                     mimetype='text/csv')
