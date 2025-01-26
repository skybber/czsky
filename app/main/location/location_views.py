from datetime import datetime
import requests
from flask_babel import lazy_gettext

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, and_

from app import db

from app.models import Location
from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.search_utils import process_paginated_session_search, get_items_per_page
from app.commons.coordinates import parse_latlon

from .location_forms import (
    LocationNewForm,
    LocationEditForm,
    SearchLocationForm,
)

from app.commons.countries import countries

main_location = Blueprint('main_location', __name__)


def _is_editable(location):
    return location.user_id == current_user.id or current_user.is_admin() or current_user.is_editor()


@main_location.route('/all-locations', methods=['GET', 'POST'])
@login_required
def all_locations():
    session.pop('location_search', None)
    return redirect(url_for('main_location.locations'))


@main_location.route('/locations', methods=['GET', 'POST'])
@login_required
def locations():
    search_form = SearchLocationForm()

    ret, page, _ = process_paginated_session_search('location_search_page', None, [
        ('location_search', search_form.q),
        ('items_per_page', search_form.items_per_page)
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_location.locations'))

    offset = (page - 1) * per_page

    locations = Location.query.filter(or_(and_(Location.is_public==True, Location.is_for_observation==True), Location.user_id==current_user.id))
    if search_form.q.data:
        locations = locations.filter(Location.name.like('%' + search_form.q.data + '%'))
    locations_for_render = locations.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=locations.count(), search=False, record_name='locations', css_framework='semantic', not_passed_args='back')

    return render_template('main/location/locations.html', locations=locations_for_render, pagination=pagination, search_form=search_form)


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
    return render_template('main/location/location_info.html', location=location, type='info', editable=_is_editable(location))


@main_location.route('/location/<int:location_id>/skyquality', methods=['GET'])
@login_required
def location_skyquality(location_id):
    """View a location info."""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not location.is_public and location.user_id != current_user.id:
        abort(404)
    return render_template('main/location/location_info.html', location=location, type='skyquality', editable=_is_editable(location))


@main_location.route('/location/<int:location_id>/observations', methods=['GET'])
@login_required
def location_observations(location_id):
    """View a location info."""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not location.is_public and location.user_id != current_user.id:
        abort(404)
    return render_template('main/location/location_info.html', location=location, type='observations', editable=_is_editable(location))


@main_location.route('/new-location', methods=['GET', 'POST'])
@login_required
def new_location():
    form = LocationNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        lat, lon = parse_latlon(form.lonlat.data)
        location = Location(
            name=form.name.data,
            longitude=lon,
            latitude=lat,
            country_code=form.country_code.data,
            descr=form.descr.data,
            bortle=form.bortle.data,
            rating=form.rating.data,
            is_public=form.is_public.data,
            is_for_observation=form.is_for_observation.data,
            time_zone=form.time_zone.data,
            iau_code=form.iau_code.data,
            user_id=current_user.id,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
            )
        db.session.add(location)
        db.session.commit()
        flash('Location successfully created', 'form-success')
        return redirect(url_for('main_location.location_edit', location_id=location.id))

    return render_template('main/location/location_edit.html', form=form, is_new=True, countries=countries)


@main_location.route('/location/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def location_edit(location_id):
    """Update location"""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not _is_editable(location):
        abort(404)
    form = LocationEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            lat, lon = parse_latlon(form.lonlat.data)
            location.name = form.name.data
            location.longitute = lon
            location.latitude = lat
            location.country_code = form.country_code.data
            location.descr = form.descr.data
            location.bortle = form.bortle.data
            location.rating = form.rating.data
            location.is_public = form.is_public.data
            location.is_for_observation = form.is_for_observation.data
            location.iau_code = form.iau_code.data
            location.update_by = current_user.id
            location.update_date = datetime.now()
            db.session.add(location)
            db.session.commit()
            flash('Location successfully updated', 'form-success')
    else:
        form.name.data = location.name
        form.lonlat.data = location.coordinates()
        form.country_code.data = location.country_code
        form.descr.data = location.descr
        form.bortle.data = location.bortle
        form.rating.data = location.rating
        form.is_public.data = location.is_public
        form.is_for_observation.data = location.is_for_observation
        form.time_zone.data = location.time_zone
        form.iau_code.data = location.iau_code

    return render_template('main/location/location_edit.html', form=form, location=location, is_new=False, countries=countries)


@main_location.route('/location/<int:location_id>/delete')
@login_required
def location_delete(location_id):
    """Request deletion of a observation."""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not _is_editable(location):
        abort(404)
    db.session.delete(location)
    flash('Location was deleted', 'form-success')
    return redirect(url_for('main_location.locations'))


@main_location.route('/location-autocomplete', methods=['GET'])
def location_autocomplete():
    search = request.args.get('q')
    locations = Location.query.filter(Location.name.like('%' + search + '%'))
    results = []
    for loc in locations.all():
        results.append({'name': loc.name, 'value': loc.id, 'text': loc.name})
    return jsonify(success=True, results=results)


@main_location.route('/location-autocomplete-unified', methods=['GET'])
def location_autocomplete_unified():
    search = request.args.get('q', '').strip()

    if not search:
        return jsonify(success=False, error=lazy_gettext("The 'q' parameter is required.")), 400

    results = []

    db_locations = Location.query.filter(Location.name.ilike(f'%{search}%')).limit(2).all()

    for loc in db_locations:
        results.append({
            'name': loc.name,
            'value': f"{loc.longitude},{loc.latitude},{loc.name}",
            'text': loc.name
        })

    if len(results) < 10:
        nominatim_limit = 10 - len(results)
    else:
        nominatim_limit = 0

    if nominatim_limit > 0:
        params = {
            'q': search,
            'format': 'json',
            'addressdetails': 1,
            'limit': nominatim_limit,
            'dedupe': 1,
        }

        headers = {
            'User-Agent': 'CzSkY/1.0 (administrator@czsky.eu)'
        }

        try:
            response = requests.get('https://nominatim.openstreetmap.org/search', params=params, headers=headers, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return jsonify(success=False, error=lazy_gettext('Error communicating with the Nominatim API.')), 500

        data = response.json()
        for item in data:
            lon = item.get('lon')
            lat = item.get('lat')
            display_name = item.get('display_name')

            if lon and lat and display_name:
                results.append({
                    'name': display_name,
                    'value': f"{lon},{lat},{display_name}",
                    'text': display_name
                })

    return jsonify(success=True, results=results)
