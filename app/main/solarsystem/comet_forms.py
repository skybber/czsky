from datetime import datetime, timedelta

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
from flask_babel import lazy_gettext

class SearchCometForm(FlaskForm):
    q = StringField('Search')

class CometFindChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=4, validators=[Length(min=1, max=4)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=10)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    mirror_x = BooleanField(lazy_gettext('Mirror X'), default=False)
    mirror_y = BooleanField(lazy_gettext('Mirror Y'), default=False)
    from_date = DateField(lazy_gettext('From Date'), id='fromdate', format = '%d/%m/%Y', default = datetime.today)
    to_date = DateField(lazy_gettext('To Date'), id='todate', format = '%d/%m/%Y', default = datetime.today)
    submit = SubmitField(lazy_gettext('Update'))