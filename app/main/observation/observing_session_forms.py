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
from app.commons.dso_utils import normalize_dso_name

from app.main.utils.validators import location_lonlat_check

DEFAULT_OBSERVATION_CONTENT = '''
## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(22:30):
Observation item1 notes
'''


class ObservationItemNewForm(FlaskForm):
    comp_notes = TextAreaField(lazy_gettext('DSO list with comment. (e.g. M3,M5:nice globulars!)'),
                               render_kw={'rows': 2})
    date_time = TimeField(lazy_gettext('Time'), format='%H:%M', default=datetime.now().time())
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    transparency = SelectField(lazy_gettext('Transparency'), choices=Transparency.choices(), coerce=Transparency.coerce,
                               default=Transparency.AVERAGE)

    def validate_comp_notes(form, field):
        if field.id != 'items-0-comp_notes':
            dsos = field.data
            if ':' in dsos:
                dsos = dsos[:dsos.index(':')]
            if len(dsos) == 0:
                raise ValidationError(lazy_gettext('Value expected.'))
            for dso_name in dsos.split(','):
                dso_name = normalize_dso_name(dso_name)
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if not dso:
                    raise ValidationError('DSO not found. Dso name:' + dso_name)

    def validate_date_time(form, field):
        if field.id != 'items-0-date_time':
            if not field.data:
                raise ValidationError(lazy_gettext('Value expected.'))


class ObservingSessionMixin:
    items = FieldList(FormField(ObservationItemNewForm), min_entries=1)
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
    notes = TextAreaField(lazy_gettext('Notes'))
    omd_content = TextAreaField(lazy_gettext('OMD Content'),
                                default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%Y-%m-%d')))
    is_public = BooleanField(lazy_gettext('Plan is public'), default=False)

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
    submit_button = SubmitField(lazy_gettext('Add Observation'))

    def validate(self):
        if not super(ObservingSessionNewForm, self).validate():
            return False
        return self.validate_date_from_to()


class ObservingSessionEditForm(FlaskForm, ObservingSessionMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update Observation'))

    def validate(self):
        if not super(ObservingSessionEditForm, self).validate():
            return False
        return self.validate_date_from_to()


class AddToObservedListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(), ])


class ObservationSessionRunPlanForm(FlaskForm):
    session_plan = HiddenField('session_plan')


class ObservingSessionExportForm(FlaskForm):
    date_from = DateField(lazy_gettext('Date From'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                          validators=[InputRequired(), ])
    date_to = DateField(lazy_gettext('Date To'), id='odate_from', format='%d/%m/%Y', default=datetime.today,
                        validators=[InputRequired(), ])
    submit_button = SubmitField(lazy_gettext('Export Observation'))
