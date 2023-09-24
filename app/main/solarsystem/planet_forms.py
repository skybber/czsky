from flask_babel import lazy_gettext
from flask_wtf import FlaskForm

from wtforms.fields import (
    DateField,
    SubmitField,
    TextAreaField,
)
from app.main.chart.chart_forms import ChartForm


class PlanetFindChartForm(ChartForm):
    date_from = DateField(lazy_gettext('From'), id='datefrom', format = '%d/%m/%Y', default = None)
    date_to = DateField(lazy_gettext('To'), id='dateto', format = '%d/%m/%Y', default = None)

class PlanetObservationLogForm(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    submit = SubmitField(lazy_gettext('Update'))
