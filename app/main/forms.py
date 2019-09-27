from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    DateField,
    FloatField,
    IntegerField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange
)

class SearchForm(FlaskForm):
    q = StringField('Search', validators=[DataRequired()])

class ObservationNewForm(FlaskForm):
    date = DateField('Date', id='odate', format = '%d/%m/%Y')
    date.data = datetime.now()
    notes = TextAreaField('Notes')
    rating = IntegerField('Ranking', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Add')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    notes = StringField('First name', validators=[Length(max=5000)])
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Update')

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
