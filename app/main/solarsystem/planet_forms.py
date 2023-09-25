from datetime import datetime

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm

from wtforms.fields import (
    DateField,
    SubmitField,
    TextAreaField,
    TimeField,
)

from wtforms.validators import (
    InputRequired,
)

from app.main.chart.chart_forms import ChartForm


class PlanetFindChartForm(ChartForm):
    date_from = DateField(lazy_gettext('From'), id='datefrom', format = '%d/%m/%Y', default = None)
    date_to = DateField(lazy_gettext('To'), id='dateto', format = '%d/%m/%Y', default = None)

class PlanetObservationLogForm(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    submit = SubmitField(lazy_gettext('Update'))
    date_from = DateField(lazy_gettext('Date From'), id='odate-from', format='%d/%m/%Y', default=datetime.today, validators=[InputRequired(), ])
    time_from = TimeField(lazy_gettext('Time From'), format='%H:%M', default=datetime.now().time(), validators=[InputRequired(), ])
