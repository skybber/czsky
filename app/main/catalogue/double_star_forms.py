from datetime import datetime

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    DateField,
    FloatField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)

from wtforms.validators import (
    InputRequired,
    Length,
)

class SearchDoubleStarForm(FlaskForm):
    q = StringField('Search')
    mag_max = FloatField(lazy_gettext('Mag max'), default=12.0)
    delta_mag_min = FloatField(lazy_gettext('Delta mag min'), default=0.0)
    delta_mag_max = FloatField(lazy_gettext('Delta mag max'), default=20.0)
    separation_min = FloatField(lazy_gettext('Separation min'), default=1.0)
    separation_max = FloatField(lazy_gettext('Separation max'), default=60.0)
    dec_min = FloatField(lazy_gettext('Dec min'), default=-35.0)
    constellation_id = IntegerField('Constellation', default=None)
    items_per_page = IntegerField(lazy_gettext('Items per page'))

class DoubleStarEditForm(FlaskForm):
    common_name = StringField(lazy_gettext('Common Name'), validators=[Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update'))
