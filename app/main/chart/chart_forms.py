from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    HiddenField,
    IntegerField,
)
from wtforms.validators import (
    Length,
)


class ChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=9, validators=[Length(min=1, max=10)])
    radius_ext = IntegerField(lazy_gettext('Field radius ext'), default=0, validators=[Length(min=0, max=1)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=7)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    mirror_x = HiddenField('mirror_x', default='false')
    mirror_y = HiddenField('mirror_y', default='false')
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
    show_dss = HiddenField('show_dss', default='false')
    show_dso_mag = HiddenField('show_dso_mag', default='false')
    eyepiece_fov = HiddenField('eyepiece_fov')
    chart_theme = HiddenField('chart_theme', default='-1')
