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
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    required
)
from flask_babel import lazy_gettext

class SearchConstellationForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    season = SelectField(lazy_gettext('Season'), choices=[
         ('All', lazy_gettext('All')),
         ('winter', lazy_gettext('Winter')),
         ('spring', lazy_gettext('Spring')),
         ('summer', lazy_gettext('Summer')),
         ('autumn',lazy_gettext('Autumn')),
         ('southern',lazy_gettext('Southern')),
    ], default='')

class ConstellationEditForm(FlaskForm):
    common_name = StringField(lazy_gettext('Common Name'), validators=[Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update'))

class ConstellationChartForm(FlaskForm):
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
    show_equatorial_grid = HiddenField('show_equatorial_grid', default='true')
    show_dso = HiddenField('show_dso', default='true')
