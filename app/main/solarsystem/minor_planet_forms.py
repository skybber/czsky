from datetime import datetime

from flask_wtf import FlaskForm
from wtforms.fields import (
    DateField,
    FloatField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import (
    InputRequired,
    NumberRange,
    Optional,
)
from flask_babel import lazy_gettext


from app.main.chart.chart_forms import ChartForm


class SearchMinorPlanetForm(FlaskForm):
    q = StringField('Search')
    season = SelectField(lazy_gettext('Season'), choices=[
        ('All', lazy_gettext('All')),
        ('winter', lazy_gettext('Winter')),
        ('spring', lazy_gettext('Spring')),
        ('summer', lazy_gettext('Summer')),
        ('autumn',lazy_gettext('Autumn')),
        ('southern',lazy_gettext('Southern')),
    ], default='')
    maglim = FloatField(lazy_gettext('Limit mag'), default=None, validators=[NumberRange(min=-30.0, max=30.0), Optional()])
    dec_min = FloatField(lazy_gettext('Dec min'), default=None, validators=[NumberRange(min=-90.0, max=90.0), Optional()])
    items_per_page = IntegerField(lazy_gettext('Items per page'))


class MinorPlanetFindChartForm(ChartForm):
    date_from = DateField(lazy_gettext('From'), id='datefrom', format = '%d/%m/%Y', default = None)
    date_to = DateField(lazy_gettext('To'), id='dateto', format = '%d/%m/%Y', default = None)
