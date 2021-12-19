from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    HiddenField,
    IntegerField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import (
    Length,
)
from flask_babel import lazy_gettext


class ChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=7, validators=[Length(min=1, max=7)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=7)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    mirror_x = BooleanField(lazy_gettext('Mirror X'), default=False)
    mirror_y = BooleanField(lazy_gettext('Mirror Y'), default=False)
    ra = HiddenField('ra')
    dec = HiddenField('dec')
    fullscreen = HiddenField('fullscreen', default='false')
    splitview = HiddenField('splitview', default='false')
    show_telrad = HiddenField('show_telrad', default='false')
    show_picker = HiddenField('show_picker', default='true')
    show_constell_shapes = HiddenField('show_constell_shapes', default='true')
    show_constell_borders = HiddenField('show_constell_borders', default='true')
    show_equatorial_grid = HiddenField('show_equatorial_grid', default='true')
    show_dso = HiddenField('show_dso', default='true')

