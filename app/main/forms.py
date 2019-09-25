from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    DateField,
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
    ranking = IntegerField('Ranking', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Add')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    notes = StringField('First name', validators=[Length(max=5000)])
    ranking = IntegerField('Ranking', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Update')

