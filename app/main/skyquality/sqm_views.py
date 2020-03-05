from datetime import datetime
import dateutil.parser

from flask import (
    abort,
    Blueprint,
    flash,
    render_template,
    request,
)

from flask_login import current_user, login_required

from app import db

from app.models import SqmDevice, SqmRecord
from app.decorators import admin_required
from app.models import SqmDevice
from app.commons.pagination import Pagination, get_page_parameter, get_page_args

from app.main.forms import (
    SearchForm,
)

from app.main.views import ITEMS_PER_PAGE
from app.commons.coordinates import mapy_cz_url, google_url

main_sqm = Blueprint('main_sqm', __name__)


@main_sqm.route('/sqm-record', methods=['GET'])
def skyquality_measurements():
    """
    record SQM measurement e.g.:
                http://localhost:5000/sqm-record?uuid=fa30b44a-166b-4b5a-8ab5-df2720ff2680&tm=2010-05-08T23:41:54&val=21.27
    """
    uuid = request.args.get('uuid')
    tm = request.args.get('tm')
    value = request.args.get('val')
    if not (uuid and tm and value):
        abort(404)
    sqm_device = SqmDevice.query.filter_by(uuid=uuid).first()
    if not sqm_device:
        abort(404)
    try:
        dt = dateutil.parser.parse(tm)
    except ValueError:
        abort(404)
    try:
        sqm_value = float(value)
    except ValueError:
        abort(404)
    sqm_record = SqmRecord(
        sqm_device_id=sqm_device.id,
        value=sqm_value,
        date_time=dt
        )
    db.session.add(sqm_record)
    db.session.commit()
    return "OK"
