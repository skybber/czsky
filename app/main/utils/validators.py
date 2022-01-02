import re
import math
from lat_lon_parser import parse as lonlat_parse
from wtforms.validators import ValidationError
from skyfield.units import Angle

from app.commons.coordinates import parse_latlon

from app.models import Location


def location_lonlat_check(form, field):
    if field.data.isdigit():
        location = Location.query.filter_by(id=int(field.data)).first()
        if location:
            return
    try:
        parse_latlon(field.data)
    except ValueError:
        raise ValidationError('Invalid coordinate format.')
