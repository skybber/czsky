from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from app.models import Location
from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.coordinates import *

from .forms import (
    LocationNewForm,
    LocationEditForm,
)

from .. import db
from .views import ITEMS_PER_PAGE

main_location = Blueprint('main_location', __name__)

@main_location.route('/locations', methods=['GET', 'POST'])
@login_required
def locations():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    locations = Location.query.filter_by(user_id=current_user.id, is_for_observation=True)
    search = False

    locations_for_render = locations.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=locations.count(), search=search, record_name='locations', css_framework='semantic')
    return render_template('main/location/locations.html', locations=locations_for_render, pagination=pagination)

@main_location.route('/location/<int:location_id>', methods=['GET'])
@main_location.route('/location/<int:location_id>/info', methods=['GET'])
@login_required
def location_info(location_id):
    """View a location info."""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not location.is_public and location.user_id != current_user.id:
        abort(404)
    url_cz_mapy = mapy_cz_url(location.longitude, location.latitude)
    url_googlee = google_url(location.longitude, location.latitude)
    url_os_map = google_url(location.longitude, location.latitude)
    return render_template('main/location/location_info.html', location=location, type='info',
                           mapy_cz_url=url_cz_mapy, google_url=url_googlee, os_map_url=url_os_map)

@main_location.route('/new-location', methods=['GET', 'POST'])
@login_required
def new_location():
    form = LocationNewForm()
    if form.validate_on_submit():
        location = Location(
            name = form.name.data,
            longitude = form.longitude.data,
            latitude = form.latitude.data,
            descr = form.descr.data,
            bortle = form.bortle.data,
            rating = form.rating.data,
            is_public = form.is_public.data,
            user_id = current_user.id,
            create_by = current_user.id,
            update_by = current_user.id,
            create_date = datetime.now(),
            update_date = datetime.now()
            )
        db.session.add(location)
        db.session.commit()
        flash('Location successfully created', 'form-success')
    return render_template('main/location/location_new.html', form=form)

@main_location.route('/location/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def location_edit(location_id):
    """Update location"""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if location.user_id != current_user.id:
        abort(404)
    form = LocationEditForm()
    if form.validate_on_submit():
        location.date = form.date.data,
        location.rating = form.rating.data
        location.notes = form.notes.data
        location.update_by = current_user.id
        location.update_date = datetime.now()
        db.session.add(location)
        db.session.commit()
        flash('Location successfully updated', 'form-success')
    return render_template('main/location/location_edit.html', form=form)
