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

from app.main.utils.validators import location_lonlat_check

SCHEDULE_TIME_FORMAT = '%H:%M'


class SearchSessionPlanForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))


class SessionPlanMixin():
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256),])
    for_date = DateField(lazy_gettext('Date'), id='odate', format = '%d/%m/%Y', default = datetime.today, validators=[InputRequired(),])
    location = StringField(lazy_gettext('Location'), validators=[InputRequired(),Length(max=256), location_lonlat_check])
    notes = TextAreaField(lazy_gettext('Notes'))
    is_public = BooleanField(lazy_gettext('Plan is public'), default=False)


class SessionPlanNewForm(FlaskForm, SessionPlanMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Add Session Plan'))


class SessionPlanEditForm(FlaskForm, SessionPlanMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update Session Plan'))


class SessionPlanScheduleFilterForm(FlaskForm):
    items_per_page = IntegerField(lazy_gettext('Items per page'))
    q = StringField(lazy_gettext('Search'))
    obj_source= HiddenField('obj_source', default='WL')
    constellation_id = IntegerField('Constellation', default=None)
    dso_type = SelectField(lazy_gettext('Object type'), choices=[
         ('All', 'All types'),
         ('GX', 'Galaxy'),
         ('GC', 'Globular Cluster'),
         ('OC', 'Open Cluster'),
         ('BN', 'Nebula'),
         ('PN', 'Planetary Nebula'),
    ], default='')
    maglim = IntegerField(lazy_gettext('Limit mag'), default=12)
    min_altitude = IntegerField(lazy_gettext('Min altitude'), default=5)
    items_per_page = IntegerField(lazy_gettext('Items per page'))
    time_from = TimeField('Time From', format=SCHEDULE_TIME_FORMAT)
    time_to = TimeField('Time From', format=SCHEDULE_TIME_FORMAT)
    not_observed = BooleanField('Not observed', default='checked')
    selected_dso_name = HiddenField(default='M1')


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
