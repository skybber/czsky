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
    Optional,
    required,
)

DEFAULT_OBSERVATION_CONTENT = '''
# Observation title
date: {date}
location: location name
observers: @user1, @user2 ...
seeing: seeing scale
sqm_1:T(time): 21.30, 21.35

general observation description, use:
* @user to reference observer
* @user:inventory_name to reference user inventory
* @user:observation to reference user observation
* #dso_name to reference dso e.g. #ngc7000
* #location to reference specific location

## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(22:30):
Observation item1 notes
'''

class ObservationItemNewForm(FlaskForm):
    deepsky_object_id_list = StringField('Deepsky object list (separated by \';\')')
    date_time = TimeField('Time', format = '%H:%M', default = datetime.now().time(), validators=(Optional(),))
    notes = TextAreaField('Notes', render_kw={'rows':2})

class ObservationNewForm(FlaskForm):
    items = FieldList(FormField(ObservationItemNewForm), min_entries = 1)
    title = StringField('Title', validators=[Length(max=256)])
    date = DateField('Date', id='odate', format = '%d/%m/%Y', default = datetime.now(), validators=(Optional(),))
    location = StringField('Location', validators=[Length(max=128)])
    rating = HiddenField('Rating', default=5)
    omd_content = TextAreaField('OMD Content',
                                default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%Y-%m-%d')),
                                validators=[Optional(),required()]
                                )
    notes = TextAreaField('Notes')
    submit = SubmitField('Add')
    advmode = HiddenField('Advanced Mode', default='false')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    rating = IntegerField('Rating', default=5, validators=[Optional(), NumberRange(min=0, max=10)])
    omd_content = TextAreaField('OMD Content', default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%d/%m/%Y')))
    notes = TextAreaField('OMD Content')
    submit = SubmitField('Update')
