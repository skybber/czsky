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
    radius = IntegerField(lazy_gettext('Field radius'), default=22, validators=[Length(min=1, max=23)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=7)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    mirror_x = HiddenField('mirror_x', default='false')
    mirror_y = HiddenField('mirror_y', default='false')
    ra = HiddenField('ra')
    dec = HiddenField('dec')
    az = HiddenField('az')
    alt = HiddenField('alt')
    longitude = HiddenField('longitude')
    latitude = HiddenField('latitude')
    chart_date_time = HiddenField('latitude')
    use_current_time = HiddenField('use_current_time', default='true')
    fullscreen = HiddenField('fullscreen', default='false')
    splitview = HiddenField('splitview', default='false')
    show_telrad = HiddenField('show_telrad', default='false')
    show_picker = HiddenField('show_picker', default='true')
    show_constell_shapes = HiddenField('show_constell_shapes', default='true')
    show_constell_borders = HiddenField('show_constell_borders', default='true')
    show_equatorial_grid = HiddenField('show_equatorial_grid', default='true')
    show_dso = HiddenField('show_dso', default='true')
    show_solar_system = HiddenField('show_solar_system', default='true')
    show_dso_mag = HiddenField('show_dso_mag', default='false')
    show_star_labels = HiddenField('show_star_labels', default='true')
    eyepiece_fov = HiddenField('eyepiece_fov')
    chart_theme = HiddenField('chart_theme', default='-1')
    dss_layer = HiddenField('dss_layer', default='false')
    optimize_traffic = HiddenField('optimize_traffic', default='false')
    is_equatorial = HiddenField('is_equatorial', default='true')
