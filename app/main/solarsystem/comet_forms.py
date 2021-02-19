from datetime import datetime, timedelta

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

class SearchCometForm(FlaskForm):
    q = StringField('Search')

class CometFindChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=7, validators=[Length(min=1, max=7)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=7)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    ra = HiddenField('ra')
    dec = HiddenField('dec')
    fullscreen = HiddenField('fullscreen')
    splitview = HiddenField('splitview')
    show_telrad = HiddenField('show_telrad', default='false')
    show_constell_shapes = HiddenField('show_constell_shapes', default='true')
    show_constell_borders = HiddenField('show_constell_borders', default='true')
    show_dso = HiddenField('show_dso', default='true')
    show_equatorial_grid = HiddenField('show_equatorial_grid', default='true')
    from_date = DateField(lazy_gettext('From Date'), id='fromdate', format = '%d/%m/%Y', default = datetime.today)
    to_date = DateField(lazy_gettext('To Date'), id='todate', format = '%d/%m/%Y', default = datetime.today)
