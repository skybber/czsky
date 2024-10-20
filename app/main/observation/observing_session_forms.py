from datetime import datetime

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    DateTimeField,
    FloatField,
    FieldList,
    FormField,
    HiddenField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import (
    InputRequired,
    Length,
    Optional,
)

from app.commons.observation_target_utils import parse_observation_targets
from app.main.utils.validators import location_lonlat_check
from app.models import Seeing, Transparency


class ObservationItemForm(FlaskForm):
    comp_notes = TextAreaField(lazy_gettext('DSO list with comment. (e.g. M3,M5:nice globulars!)'),
                               render_kw={'rows': 2})
    date_from = TimeField(lazy_gettext('Time From'), format='%H:%M', default=datetime.now().time())
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    transparency = SelectField(lazy_gettext('Transparency'), choices=Transparency.choices(), coerce=Transparency.coerce,
                               default=Transparency.AVERAGE)
    telescope = SelectField(lazy_gettext('Telescope'), coerce=int)
    eyepiece = SelectField(lazy_gettext('Eyepiece'), coerce=int)
    filter = SelectField(lazy_gettext('Filter'), coerce=int)

    def validate_comp_notes(form, field):
        if field.id != 'items-0-comp_notes':
            targets = field.data
            if ':' in targets:
                targets = targets[:targets.index(':')]
            if len(targets) == 0:
                raise ValidationError(lazy_gettext('Value expected.'))
            _, _, _, _, _, _, not_found = parse_observation_targets(targets)
            if not_found:
                msg = lazy_gettext('Unknown targets:') + ','.join(not_found)
                raise ValidationError(lazy_gettext('Unknown targets:') + ','.join(not_found))


class ObservingSessionMixin:
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256), ])
    rating = HiddenField(lazy_gettext('Rating'), default=0)
    date_from = DateTimeField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                              validators=[InputRequired(), ])
    date_to = DateTimeField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y %H:%M', default=datetime.today,
                            validators=[InputRequired(), ])
    location = StringField(lazy_gettext('Location'),
                           validators=[InputRequired(), Length(max=256), location_lonlat_check])
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    faintest_star = FloatField(lazy_gettext('Faintest Star'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    transparency = SelectField(lazy_gettext('Transparency'), choices=Transparency.choices(), coerce=Transparency.coerce,
                               default=Transparency.AVERAGE)
    weather = StringField(lazy_gettext('Weather'))
    equipment = StringField(lazy_gettext('Equipment'))
    default_telescope = SelectField(lazy_gettext('Default telescope'), coerce=int)
    notes = TextAreaField(lazy_gettext('Notes'))
    is_public = BooleanField(lazy_gettext('Session is public'), default=False)
    is_finished = BooleanField(lazy_gettext('Session is finished'), default=False)
    is_active = BooleanField(lazy_gettext('Session is active'), default=False)

    def validate_date_from_to(self):
        if self.date_from.data and self.date_to.data and self.date_from.data > self.date_to.data:
            msg = lazy_gettext('Date from must be before date to.')
            self.date_from.errors.append(msg)
            msg = lazy_gettext('Date to must be after date from.')
            self.date_to.errors.append(msg)
            return False
        return True


class ObservingSessionNewForm(FlaskForm, ObservingSessionMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Create Observing Session'))

    def validate(self, extra_validators=None):
        if not super(ObservingSessionNewForm, self).validate():
            return False
        return self.validate_date_from_to()


class ObservingSessionEditForm(FlaskForm, ObservingSessionMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update Observing Session'))

    def validate(self, extra_validators=None):
        if not super(ObservingSessionEditForm, self).validate():
            return False
        return self.validate_date_from_to()


class ObservingSessionItemsEditForm(FlaskForm):
    goback = HiddenField(default='false')
    items = FieldList(FormField(ObservationItemForm), min_entries=1)
    submit_button = SubmitField(lazy_gettext('Update Items'))


class AddToObservedListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(), ])


class ObservingSessionRunPlanForm(FlaskForm):
    session_plan = HiddenField('session_plan')


class ObservingSessionExportForm(FlaskForm):
    submit_button = SubmitField(lazy_gettext('Export Observing Session'))

