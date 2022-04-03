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
from app.commons.dso_utils import normalize_dso_name


class StandaloneObservationMixin:
    target = StringField(lazy_gettext('Target'), validators=[InputRequired(), ])
    date_from = DateTimeField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                              validators=[InputRequired(), ])
    date_to = DateTimeField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                            validators=[InputRequired(), ])
    location = StringField(lazy_gettext('Location'),
                           validators=[InputRequired(), Length(max=256), location_lonlat_check])
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    faintest_star = FloatField(lazy_gettext('Faintest Star'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    telescope = SelectField(lazy_gettext('Telescope'), coerce=int)
    eyepiece = SelectField(lazy_gettext('Eyepiece'), coerce=int)
    filter = SelectField(lazy_gettext('Filter'), coerce=int)
    notes = TextAreaField(lazy_gettext('Notes'))

    def validate_target(self, field):
        target_names = self.target.data.split(',')
        unknown_targets = []
        for target_name in target_names:
            normalized_name = normalize_dso_name(target_name)
            dso = DeepskyObject.query.filter_by(name=normalized_name).first()
            if not dso:
                unknown_targets.append(target_name)
        if len(unknown_targets) > 0:
            msg = lazy_gettext('Unknown targets:') + ','.join(unknown_targets)
            self.target.errors.append(msg)
            return False
        return True

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

