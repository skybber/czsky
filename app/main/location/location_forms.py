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

from app.commons.coordinates import lonlat_check

class LocationMixin():
    name = StringField('Name', validators=[Length(max=128)])
    lonlat = StringField('Longitude', validators=[Length(max=256), lonlat_check])
    descr = TextAreaField('Notes')
    bortle = FloatField('Bortle', validators=[NumberRange(min=0.0, max=9.0)])
    rating = IntegerField('Rating', default=5, validators=[NumberRange(min=0, max=10)])
    is_for_observation = BooleanField('Is suitable for observation', default=True)
    is_public = BooleanField('Is public', default=True)

class LocationNewForm(FlaskForm, LocationMixin):
    submit = SubmitField('Add location')

class LocationEditForm(FlaskForm, LocationMixin):
    submit = SubmitField('Update location')
