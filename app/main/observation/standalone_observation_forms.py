from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    DateField,
    DateTimeField,
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

from app.models import Seeing, Transparency, DeepskyObject

from app.main.utils.validators import location_lonlat_check
from app.commons.observation_target_utils import parse_observation_targets


class StandaloneObservationMixin:
    observing_session_id = HiddenField(default='false')
    target = StringField(lazy_gettext('Target'), validators=[InputRequired(), ])
    date_from = DateTimeField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                              validators=[InputRequired(), ])
    date_to = DateTimeField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                            validators=[InputRequired(), ])
    location = StringField(lazy_gettext('Location'),
                           validators=[Length(max=256), ])
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    faintest_star = FloatField(lazy_gettext('Faintest Star'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    telescope = SelectField(lazy_gettext('Telescope'), coerce=int)
    eyepiece = SelectField(lazy_gettext('Eyepiece'), coerce=int)
    filter = SelectField(lazy_gettext('Filter'), coerce=int)
    notes = TextAreaField(lazy_gettext('Notes'))

    def validate_target(self, field):
        _, _, _, _, _, not_found = parse_observation_targets(self.target.data)
        if not_found:
            msg = lazy_gettext('Unknown targets:') + ','.join(not_found)
            self.target.errors.append(msg)
            return False
        return True

    def validate_location(self, field):
        if self.observing_session_id.data:
            return True
        return location_lonlat_check(self, field)

    def validate_date_from_to(self):
        if self.date_from.data and self.date_to.data and self.date_from.data > self.date_to.data:
            msg = lazy_gettext('Date from must be before date to.')
            self.date_from.errors.append(msg)
            msg = lazy_gettext('Date to must be after date from.')
            self.date_to.errors.append(msg)
            return False
        return True


class StandaloneObservationNewForm(FlaskForm, StandaloneObservationMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Create Observation'))

    def validate(self):
        if not super(StandaloneObservationNewForm, self).validate():
            return False
        return self.validate_date_from_to()


class StandaloneObservationEditForm(FlaskForm, StandaloneObservationMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update Observation'))

    def validate(self):
        if not super(StandaloneObservationEditForm, self).validate():
            return False
        return self.validate_date_from_to()


class SearchStandaloneObservationForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    items_per_page = IntegerField(lazy_gettext('Items per page'))
