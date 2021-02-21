from datetime import datetime

from flask_wtf import FlaskForm
from flask_babel import lazy_gettext
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


class SearchForm(FlaskForm):
    q = StringField('Search')
    items_per_page = IntegerField(lazy_gettext('Items per page'))

