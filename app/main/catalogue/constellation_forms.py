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
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    required
)

class SearchConstellationForm(FlaskForm):
    q = StringField('Search')
    season = SelectField('Season', choices=[
         ('All', 'All'),
         ('winter', 'Winter'),
         ('spring', 'Spring'),
         ('summer', 'Summer'),
         ('autumn','Autumn'),
         ('southern','Southern'),
    ])

class ConstellationEditForm(FlaskForm):
    common_name = StringField('Common Name', validators=[Length(max=256)])
    text = TextAreaField('Text')
    submit = SubmitField('Update')
