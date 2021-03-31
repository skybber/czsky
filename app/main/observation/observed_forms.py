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
from flask_babel import lazy_gettext

from app.models import DeepskyObject
from app.commons.dso_utils import normalize_dso_name


class AddToObservedListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(),])