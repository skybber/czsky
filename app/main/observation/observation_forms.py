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
    comp_notes = TextAreaField(lazy_gettext('DSO list with comment. (e.g. M3,M5:nice globulars!)'), render_kw={'rows': 2})
    date_time = TimeField(lazy_gettext('Time'), format='%H:%M', default=datetime.now().time())
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    transparency = SelectField(lazy_gettext('Transparency'), choices=Transparency.choices(), coerce=Transparency.coerce, default=Transparency.AVERAGE)

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


class ObservationMixin:
    items = FieldList(FormField(ObservationItemNewForm), min_entries = 1)
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256),])
    date = DateField(lazy_gettext('Date'), id='odate', format='%d/%m/%Y', default=datetime.today, validators=[InputRequired(),])
    location = StringField(lazy_gettext('Location'), validators=[InputRequired(), Length(max=256), location_lonlat_check])
    sqm = FloatField(lazy_gettext('Sqm'), validators=[Optional()])
    seeing = SelectField(lazy_gettext('Seeing'), choices=Seeing.choices(), coerce=Seeing.coerce, default=Seeing.AVERAGE)
    transparency = SelectField(lazy_gettext('Transparency'), choices=Transparency.choices(), coerce=Transparency.coerce, default=Transparency.AVERAGE)
    rating = HiddenField(lazy_gettext('Rating'), default=0)
    notes = TextAreaField(lazy_gettext('Notes'))
    omd_content = TextAreaField(lazy_gettext('OMD Content'), default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%Y-%m-%d')))
    advmode = HiddenField('Advanced Mode', default='false')
    is_public = BooleanField(lazy_gettext('Plan is public'), default=False)


class ObservationNewForm(FlaskForm, ObservationMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Add Observation'))


class ObservationEditForm(FlaskForm, ObservationMixin):
    goback = HiddenField(default='false')
    submitt_button = SubmitField(lazy_gettext('Update Observation'))


class AddToObservedListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(),])


class ObservationRunPlanForm(FlaskForm):
    session_plan = HiddenField('session_plan')
