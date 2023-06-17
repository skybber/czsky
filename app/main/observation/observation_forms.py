from datetime import datetime

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    DateField,
    SubmitField,
)
from wtforms.validators import (
    InputRequired,
)


class ObservationExportForm(FlaskForm):
    date_from = DateField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                          validators=[InputRequired(), ])
    date_to = DateField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                        validators=[InputRequired(), ])
    submit_button = SubmitField(lazy_gettext('Export Observing Session'))

