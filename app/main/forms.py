from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    IntegerField,
    StringField,
    SubmitField
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
    ranking = IntegerField('Ranking', validators=[NumberRange(min=0, max=10)])
    notes = StringField('First name', validators=[Length(max=5000)])
    submit = SubmitField('Confirm')

class ObservationEditForm(FlaskForm):
    ranking = IntegerField('Ranking', validators=[NumberRange(min=0, max=10)])
    notes = StringField('First name', validators=[Length(max=5000)])
    submit = SubmitField('Confirm')

