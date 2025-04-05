import os
from datetime import datetime
import base64
from io import StringIO, BytesIO
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

from app import db, csrf

from .user_object_list_forms import (
    UserObjectListNewForm,
    UserObjectListEditForm,
    UserObjectListItemsEditForm,
)

from app.models import (
    Observation,
    UserObjectList,
    Planet,
    User,
)

from app.commons.search_utils import get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter
from app.commons.observation_target_utils import set_observation_targets

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
    common_chart_pdf_img,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.prevnext_utils import get_default_chart_iframe_url, parse_prefix_obj_id

main_user_object_list = Blueprint('main_user_object_list', __name__)


@main_user_object_list.route('/user-object-lists', methods=['GET', 'POST'])
@login_required
def user_object_lists():
    """View user object lists."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    user_object_lists = UserObjectList.query.filter_by(user_id=current_user.id).order_by(UserObjectList.create_date.desc())
    search = False

    obs_sessions_for_render = user_object_lists.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=user_object_lists.count(), search=search, record_name='user_object_list', css_framework='semantic')
    return render_template('main/observation/user_object_lists.html', user_object_lists=obs_sessions_for_render, pagination=pagination, user=None)


@main_user_object_list.route('/user-user-object-lists/<int:user_id>', methods=['GET', 'POST'])
def user_user_object_lists(user_id):
    """View user object lists of given user."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    user_object_lists = UserObjectList.query.filter_by(user_id=user_id, is_public=True) \
        .order_by(UserObjectList.date_from.desc())
    search = False

    obs_sessions_for_render = user_object_lists.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=user_object_lists.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/user_object_lists.html', user_object_lists=obs_sessions_for_render, pagination=pagination, user=user)


def _check_user_object_list(user_object_list, allow_public=False):
    if user_object_list is None:
        abort(404)
    if current_user.is_anonymous:
        if user_object_list.is_public:
            return False
        abort(404)
    elif user_object_list.user_id != current_user.id:
        if allow_public and user_object_list.is_public:
            return False
        abort(404)

    return True


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>', methods=['GET'])
@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/info', methods=['GET'])
def user_object_list_info(user_object_list_id):
    """View a user object list."""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    return render_template('main/observation/user_object_list_info.html', user_object_list=user_object_list, type='info',
                           is_mine_user_object_list=is_mine_user_object_list)


@main_user_object_list.route('/new-user_object_list', methods=['GET', 'POST'])
@login_required
def new_user_object_list():
    """Create new user_object_list"""
    form = UserObjectListNewForm()

    if request.method == 'POST' and form.validate_on_submit():
        user_object_list = UserObjectList(
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
            rating=int(form.rating.data) * 2,
            weather=form.weather.data,
            equipment=form.equipment.data,
            notes=form.notes.data,
            default_telescope_id=form.default_telescope.data,
            is_public = form.is_public.data,
            is_finished = form.is_finished.data,
            is_active = form.is_active.data,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )

        if user_object_list.is_finished:
            user_object_list.is_active = False

        if user_object_list.is_active:
            _deactivate_all_user_user_object_lists()

        db.session.add(user_object_list)
        db.session.commit()
        flash(gettext('Observing session successfully created'), 'form-success')
        return redirect(url_for('main_user_object_list.user_object_list_edit', user_object_list_id=user_object_list.id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/user_object_list_edit.html', form=form, is_new=True, location=location,
                           location_position=location_position, user_object_list=None)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/edit', methods=['GET', 'POST'])
@login_required
def user_object_list_edit(user_object_list_id):
    """Update user_object_list"""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list)

    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    form = UserObjectListEditForm()
    form.default_telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]

    if request.method == 'POST':
        if form.validate_on_submit():
            location_position = None
            location_id = None
            if isinstance(form.location.data, int) or form.location.data.isdigit():
                location_id = int(form.location.data)
            else:
                location_position = form.location.data

            user_object_list.user_id = current_user.id
            user_object_list.title = form.title.data
            user_object_list.date_from = form.date_from.data
            user_object_list.date_to = form.date_to.data
            user_object_list.location_id = location_id
            user_object_list.location_position = location_position
            user_object_list.sqm = form.sqm.data
            user_object_list.faintest_star = form.faintest_star.data
            user_object_list.seeing = form.seeing.data
            user_object_list.transparency = form.transparency.data
            user_object_list.rating = int(form.rating.data) * 2
            user_object_list.weather = form.weather.data
            user_object_list.equipment = form.equipment.data
            user_object_list.notes = form.notes.data
            user_object_list.default_telescope_id = form.default_telescope.data
            user_object_list.update_by = current_user.id
            user_object_list.update_date = datetime.now()
            user_object_list.is_public = form.is_public.data
            user_object_list.is_finished = form.is_finished.data
            if user_object_list.is_finished:
                user_object_list.is_active = False
                activated = False
            else:
                activated = form.is_active.data and user_object_list.is_active != form.is_active.data
                user_object_list.is_active = form.is_active.data

            if activated:
                _deactivate_all_user_user_object_lists()
                user_object_list.is_active = True

            db.session.add(user_object_list)
            db.session.commit()

            flash(gettext('Observing session successfully updated'), 'form-success')

            if form.goback.data == 'true':
                return redirect(url_for('main_user_object_list.user_object_list_info', user_object_list_id=user_object_list.id))
            return redirect(url_for('main_user_object_list.user_object_list_edit', user_object_list_id=user_object_list.id))
    else:
        form.title.data = user_object_list.title
        form.date_from.data = user_object_list.date_from
        form.date_to.data = user_object_list.date_to
        form.location.data = user_object_list.location_id if user_object_list.location_id is not None else user_object_list.location_position
        form.sqm.data = user_object_list.sqm
        form.faintest_star.data = user_object_list.faintest_star
        form.seeing.data = user_object_list.seeing if user_object_list.seeing else Seeing.AVERAGE
        form.transparency.data = user_object_list.transparency if user_object_list.transparency else Transparency.AVERAGE
        form.rating.data = user_object_list.rating // 2 if user_object_list.rating is not None else 0
        form.weather.data = user_object_list.weather
        form.equipment.data = user_object_list.equipment
        form.notes.data = user_object_list.notes
        form.default_telescope.data = user_object_list.default_telescope_id
        form.is_public.data = user_object_list.is_public
        form.is_finished.data = user_object_list.is_finished
        form.is_active.data = user_object_list.is_active

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/user_object_list_edit.html', form=form, is_new=False, user_object_list=user_object_list,
                           location=location, location_position=location_position)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/items-edit', methods=['GET', 'POST'])
@login_required
def user_object_list_items_edit(user_object_list_id):
    """Update user_object_list items"""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list)

    form = UserObjectListItemsEditForm()

    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    eyepieces = Eyepiece.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    filters = Filter.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()

    if request.method == 'POST':
        for item_form in form.items:
            _assign_equipment_choices(item_form, telescopes, eyepieces, filters)
        # set fake item
        form.items[0].telescope.data = -1
        form.items[0].eyepiece.data = -1
        form.items[0].filter.data = -1
        if form.validate_on_submit():
            for observation in user_object_list.observations:
                observation.deepsky_objects = []
                db.session.delete(observation)
            user_object_list.observations.clear()
            for item_form in form.items[1:]:
                if user_object_list.date_from.day != user_object_list.date_to.day:
                    if item_form.date_from.data.hour >= 12:
                        item_time = datetime.combine(user_object_list.date_from, item_form.date_from.data)
                    else:
                        item_time = datetime.combine(user_object_list.date_to, item_form.date_from.data)
                else:
                    item_time = datetime.combine(user_object_list.date_from, item_form.date_from.data)

                if ':' in item_form.comp_notes.data:
                    targets, notes = item_form.comp_notes.data.split(':', 1)
                else:
                    targets, notes = item_form.comp_notes.data.strip(), ''

                observation = Observation(
                    user_object_list_id=user_object_list.id,
                    user_id=current_user.id,
                    date_from=item_time,
                    date_to=item_time,
                    notes=notes,
                    telescope_id=item_form.telescope.data if item_form.telescope.data != -1 else None,
                    eyepiece_id=item_form.eyepiece.data if item_form.eyepiece.data != -1 else None,
                    filter_id=item_form.filter.data if item_form.filter.data != -1 else None,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                )
                user_object_list.observations.append(observation)

                set_observation_targets(observation, targets)

            db.session.add(user_object_list)
            db.session.commit()

            if form.goback.data == 'true':
                return redirect(url_for('main_user_object_list.user_object_list_info', user_object_list_id=user_object_list.id))
            return redirect(url_for('main_user_object_list.user_object_list_items_edit', user_object_list_id=user_object_list.id))
    else:
        _assign_equipment_choices(form.items[0], telescopes, eyepieces, filters)
        for oi in user_object_list.observations:
            oif = form.items.append_entry()
            _assign_equipment_choices(oif, telescopes, eyepieces, filters)
            if oi.target_type == ObservationTargetType.DBL_STAR:
                targets_comp = oi.double_star.get_common_norm_name()
            elif oi.target_type == ObservationTargetType.PLANET:
                targets_comp = Planet.get_by_iau_code(oi.planet.iau_code).get_localized_name()
            elif oi.target_type == ObservationTargetType.COMET:
                targets_comp = oi.comet.designation
            elif oi.target_type == ObservationTargetType.M_PLANET:
                targets_comp = oi.minor_planet.designation
            else:
                targets_comp = ','.join([dso.name for dso in oi.deepsky_objects])
            targets_comp += ':'
            oif.comp_notes.data = targets_comp + oi.notes
            oif.date_from.data = oi.date_from
            oif.telescope.data = oi.telescope_id if oi.telescope_id is not None else -1
            oif.eyepiece.data = oi.eyepiece_id if oi.eyepiece_id is not None else -1
            oif.filter.data = oi.filter_id if oi.filter_id is not None else -1

    return render_template('main/observation/user_object_list_items_edit.html', form=form, user_object_list=user_object_list)


def _assign_equipment_choices(form_item, telescopes, eyepieces, filters):
    form_item.telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]
    form_item.eyepiece.choices = [(-1, "---")] + [(e.id, e.name) for e in eyepieces]
    form_item.filter.choices = [(-1, "---")] + [(f.id, f.name) for f in filters]


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/delete')
@login_required
def user_object_list_delete(user_object_list_id):
    """Request deletion of a user_object_list."""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list)
    db.session.delete(user_object_list)
    db.session.commit()
    flash(gettext('Observation was deleted'), 'form-success')
    return redirect(url_for('main_user_object_list.user_object_lists'))


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def user_object_list_chart(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    form = ChartForm()

    prefix, obj_id = parse_prefix_obj_id(request.args.get('obj_id'))

    user_object_list_item = None

    for oitem in user_object_list.observations:
        if oitem.target_type == ObservationTargetType.DSO:
            for oitem_dso in oitem.deepsky_objects:
                if obj_id is None or oitem_dso.id == obj_id:
                    user_object_list_item = oitem
                    break
        elif oitem.target_type == ObservationTargetType.DBL_STAR:
            if obj_id is None or oitem.double_star_id == obj_id:
                user_object_list_item = oitem
        if user_object_list_item is not None:
            break

    common_ra_dec_dt_fsz_from_request(form,
                                      user_object_list_item.get_ra() if user_object_list_item else None,
                                      user_object_list_item.get_dec() if user_object_list_item else None)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(user_object_list_item, back='observation', back_id=user_object_list.id)

    return render_template('main/observation/user_object_list_info.html', fchart_form=form, type='chart',
                           user_object_list=user_object_list, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_user_object_list=is_mine_user_object_list,
                           back='observation', back_id=user_object_list.id)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart-pos-img', methods=['GET'])
def user_object_list_chart_pos_img(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_user_object_list(user_object_list)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart-pdf', methods=['GET'])
def user_object_list_chart_pdf(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_user_object_list(user_object_list)

    img_bytes = common_chart_pdf_img(None, None, highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart-legend-img', methods=['GET'])
def user_object_list_chart_legend_img(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    img_bytes = common_chart_legend_img(None, None)
    return send_file(img_bytes, mimetype='image/png')

