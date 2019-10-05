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

from .forms import (
    SearchForm,
)

from .. import db
from .views import ITEMS_PER_PAGE
from app.commons.coordinates import mapy_cz_url, google_url

main_skyquality = Blueprint('main_skyquality', __name__)

@main_skyquality.route('/skyquality-locations', methods=['GET', 'POST'])
def skyquality_locations():
    search_form = SearchForm()

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    locations = Location.query.filter(Location.is_for_observation == True)
    search = False
    if search_form.q.data:
        locations = locations.filter(Location.name.like('%' + search_form.q.data + '%'))
        search = True

    locations_for_render = locations.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=locations.count(), search=search, record_name='locations', css_framework='semantic')
    return render_template('main/skyquality/skyquality_locations.html', locations=locations_for_render, pagination=pagination, search_form=search_form)


@main_skyquality.route('/skyquality-location/<int:location_id>', methods=['GET'])
@main_skyquality.route('/skyquality-location/<int:location_id>/info', methods=['GET'])
def skyquality_location_info(location_id):
    """View a skyquality location info."""
    location = Location.query.filter_by(id=location_id).first()
    if location is None:
        abort(404)
    if not location.is_public and (not current_user or location.user_id != current_user.id):
        abort(404)
    url_mapy_cz = mapy_cz_url(location.longitude, location.latitude)
    url_google = google_url(location.longitude, location.latitude)
    url_os_map = google_url(location.longitude, location.latitude)
    return render_template('main/skyquality/skyquality_location_info.html', location=location, type='info',
                           mapy_cz_url=url_mapy_cz, google_url=url_google, os_map_url=url_os_map)

@main_skyquality.route('/skyquality-measurements', methods=['GET', 'POST'])
def skyquality_measurements():
    return render_template('main/skyquality/measurements.html')

