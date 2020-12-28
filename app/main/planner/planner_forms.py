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
from wtforms.widgets import (
    HiddenInput,
)
from flask_babel import lazy_gettext

class SearchSessionPlanForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))

class SessionPlanMixin():
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256),])
    for_date = DateField(lazy_gettext('Date'), id='odate', format = '%d/%m/%Y', default = datetime.today, validators=[InputRequired(),])
    location_id = IntegerField(lazy_gettext('Location'), validators=[InputRequired()])
    notes = TextAreaField(lazy_gettext('Notes'))

class SessionPlanNewForm(FlaskForm, SessionPlanMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Add Session Plan'))

class SessionPlanEditForm(FlaskForm, SessionPlanMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update Session Plan'))

class AddToSessionPlanForm(FlaskForm):
    session_plan_id = IntegerField(widget=HiddenInput())
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(),])

class AddToWishListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(),])

class SearchWishListForm(FlaskForm):
    season = SelectField(lazy_gettext('Season'), choices=[
         ('All', lazy_gettext('All')),
         ('winter', lazy_gettext('Winter')),
         ('spring', lazy_gettext('Spring')),
         ('summer', lazy_gettext('Summer')),
         ('autumn',lazy_gettext('Autumn')),
         ('southern',lazy_gettext('Southern')),
    ], default='')


class PlannerAddForm(FlaskForm):
    season = SelectField(lazy_gettext('Object Type'), choices=[
         ('All', lazy_gettext('All')),
         ('GX', lazy_gettext('Galaxy')),
         ('GC', lazy_gettext('Globular Cluster')),
         ('OC', lazy_gettext('Open Cluster')),
         ('PN', lazy_gettext('Planetary Nebula')),
         ('BN', lazy_gettext('Bright Nebula')),
         ('DN', lazy_gettext('Dark Nebula')),
         ('GALCL', lazy_gettext('Galaxy Cluster')),
         ('PartOf', lazy_gettext('Part Of')),
    ], default='')
    constellation = SelectField(lazy_gettext('Object Type'), choices=[
         ('All', lazy_gettext('All')),
         ('GX', lazy_gettext('Galaxy')),
         ('GC', lazy_gettext('Globular Cluster')),
         ('OC', lazy_gettext('Open Cluster')),
         ('PN', lazy_gettext('Planetary Nebula')),
         ('BN', lazy_gettext('Bright Nebula')),
         ('DN', lazy_gettext('Dark Nebula')),
         ('GALCL', lazy_gettext('Galaxy Cluster')),
         ('PartOf', lazy_gettext('Part Of')),
    ], default='')
