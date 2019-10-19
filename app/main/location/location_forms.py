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

class LocationNewForm(FlaskForm):
    name = StringField('Name', validators=[Length(max=128)])
    longitude = StringField('Longitude', validators=[Length(max=128)])
    latitude = StringField('Latitude', validators=[Length(max=128)])
    descr = TextAreaField('Notes')
    bortle = FloatField('Bortle', validators=[NumberRange(min=0.0, max=9.0)])
    is_public = BooleanField('Is public')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Add')

class LocationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    notes = TextAreaField('Notes')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Update')