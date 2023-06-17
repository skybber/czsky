import pytz
from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    FloatField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    InputRequired,
    Length,
    NumberRange,
    Optional,
)

from app.commons.coordinates import lonlat_check


class LocationMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    lonlat = StringField(lazy_gettext('Position'), validators=[Length(max=256), lonlat_check])
    descr = TextAreaField(lazy_gettext('Notes'))
    bortle = FloatField(lazy_gettext('Bortle'), validators=[NumberRange(min=0.0, max=9.0)])
    rating = IntegerField(lazy_gettext('Rating'), default=5, validators=[NumberRange(min=0, max=10)])
    is_for_observation = BooleanField(lazy_gettext('Is suitable for observation'), default=True)
    is_public = BooleanField(lazy_gettext('Is public'), default=True)
    country_code = StringField(lazy_gettext('Country'), validators=[InputRequired(),])
    time_zone = SelectField(lazy_gettext('Time Zone'), choices=pytz.all_timezones, validators=[Optional()])
    iau_code = IntegerField(lazy_gettext('IAU code'), validators=[Optional()])


class LocationNewForm(FlaskForm, LocationMixin):
    submit = SubmitField(lazy_gettext('Add location'))


class LocationEditForm(FlaskForm, LocationMixin):
    submit = SubmitField(lazy_gettext('Update location'))


class SearchLocationForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    items_per_page = IntegerField(lazy_gettext('Items per page'))
