from datetime import datetime

from flask_wtf import FlaskForm
from wtforms.fields import (
    DateField,
    FloatField,
    IntegerField,
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


class SearchCometForm(FlaskForm):
    q = StringField('Search')
    maglim = FloatField(lazy_gettext('Limit mag'), default=None, validators=[NumberRange(min=-30.0, max=30.0), Optional()])
    dec_min = FloatField(lazy_gettext('Dec min'), default=None, validators=[NumberRange(min=-90.0, max=90.0), Optional()])
    items_per_page = IntegerField(lazy_gettext('Items per page'))


class SearchCobsForm(FlaskForm):
    items_per_page = IntegerField(lazy_gettext('Items per page'))


class CometFindChartForm(ChartForm):
    date_from = DateField(lazy_gettext('From'), id='datefrom', format = '%d/%m/%Y', default = None)
    date_to = DateField(lazy_gettext('To'), id='dateto', format = '%d/%m/%Y', default = None)


class CometObservationLogForm(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    submit = SubmitField(lazy_gettext('Update'))
    date_from = DateField(lazy_gettext('Date From'), id='odate-from', format='%d/%m/%Y', default=datetime.today, validators=[InputRequired(), ])
    time_from = TimeField(lazy_gettext('Time From'), format='%H:%M', default=datetime.now().time(), validators=[InputRequired(), ])
