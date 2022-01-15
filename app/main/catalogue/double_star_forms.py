from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    DateField,
    FloatField,
    FieldList,
    FormField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    required
)
from flask_babel import lazy_gettext


class SearchDoubleStarForm(FlaskForm):
    q = StringField('Search')
    mag_first_max = FloatField(lazy_gettext('Mag max'), default=10.0)
    delta_mag_min = FloatField(lazy_gettext('Delta mag min'), default=0.0)
    separation_min = FloatField(lazy_gettext('Separation min'), default=1.0)
    items_per_page = IntegerField(lazy_gettext('Items per page'))
