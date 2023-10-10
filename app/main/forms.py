from datetime import datetime
from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField
)

from wtforms.validators import (
    InputRequired,
)

class SearchForm(FlaskForm):
    q = StringField('Search')
    items_per_page = IntegerField(lazy_gettext('Items per page'))

class ObservationLogForm(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    telescope = SelectField(lazy_gettext('Telescope'), coerce=int)
    eyepiece = SelectField(lazy_gettext('Eyepiece'), coerce=int)
    filter = SelectField(lazy_gettext('Filter'), coerce=int)
    submit = SubmitField(lazy_gettext('Update'))
    date_from = DateField(lazy_gettext('Date From'), id='odate-from', format='%d/%m/%Y', default=datetime.today, validators=[InputRequired(), ])
    time_from = TimeField(lazy_gettext('Time From'), format='%H:%M', default=datetime.now().time(), validators=[InputRequired(), ])

class ObservationLogNoFilterForm(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    telescope = SelectField(lazy_gettext('Telescope'), coerce=int)
    eyepiece = SelectField(lazy_gettext('Eyepiece'), coerce=int)
    submit = SubmitField(lazy_gettext('Update'))
    date_from = DateField(lazy_gettext('Date From'), id='odate-from', format='%d/%m/%Y', default=datetime.today, validators=[InputRequired(), ])
    time_from = TimeField(lazy_gettext('Time From'), format='%H:%M', default=datetime.now().time(), validators=[InputRequired(), ])
