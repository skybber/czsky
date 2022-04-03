from datetime import datetime

from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    DateField,
    DateTimeField,
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
    InputRequired,
)
from flask_babel import lazy_gettext


class ObservationExportForm(FlaskForm):
    date_from = DateField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                          validators=[InputRequired(), ])
    date_to = DateField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                        validators=[InputRequired(), ])
    submit_button = SubmitField(lazy_gettext('Export Observing Session'))

