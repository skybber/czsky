from flask_babel import lazy_gettext

from wtforms.fields import (
    DateField,
)

from app.main.chart.chart_forms import ChartForm


class PlanetMoonsFindChartForm(ChartForm):
    date_from = DateField(lazy_gettext('From'), id='datefrom', format = '%d/%m/%Y', default = None)
    date_to = DateField(lazy_gettext('To'), id='dateto', format = '%d/%m/%Y', default = None)
