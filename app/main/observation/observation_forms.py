from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    DateField,
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
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    required
)

DEFAULT_OBSERVATION_CONTENT = '''
# Observation title
:location: location_name
:date: {date}
:observers: @user1, @user2 ...
:seeing: seeing scale
:sqm_1:T(time): 21.30, 21.35

general observation description, use:
* @user to reference observer
* @user:inventory_name to reference user inventory
* @user:observation to reference user observation
* #dso_name to reference dso e.g. #ngc7000
* #location to reference specific location

## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(21:30):
Observation item1 notes
'''

class ObservationItemNewForm(FlaskForm):
    deepsky_object_id_list = StringField('Deepsky object list (separated by \';\')', validators=[required()])
    date_time = TimeField('Time', format = '%H:%M', default = datetime.now())
    notes = TextAreaField('Notes', render_kw={'rows':2})

class ObservationNewForm(FlaskForm):
    date = DateField('Date', id='odate', format = '%d/%m/%Y', default = datetime.now())
    rating = HiddenField('Rating', default=1)
    omd_content = TextAreaField('OMD Content', default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%d/%m/%Y')))
    notes = TextAreaField('Notes', validators=[required()])
    submit = SubmitField('Add')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    omd_content = TextAreaField('OMD Content', default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%d/%m/%Y')))
    notes = TextAreaField('OMD Content')
    submit = SubmitField('Update')
