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

DEFAULT_OBSERVATION_CONTENT = '''
## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(22:30):
Observation item1 notes
'''

class ObservationItemNewForm(FlaskForm):
    deepsky_object_id_list = StringField(lazy_gettext('DSO list optionally with comment. (e.g. M3,M5:nice globulars!)'))
    date_time = TimeField(lazy_gettext('Time'), format = '%H:%M', default = datetime.now().time())
    notes = TextAreaField(lazy_gettext('Notes'), render_kw={'rows':2})

    def validate_deepsky_object_id_list(form, field):
        if field.id != 'items-0-deepsky_object_id_list':
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


class ObservationMixin():
    items = FieldList(FormField(ObservationItemNewForm), min_entries = 1)
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256),])
    date = DateField(lazy_gettext('Date'), id='odate', format = '%d/%m/%Y', default = datetime.today, validators=[InputRequired(),])
    location_id = IntegerField(lazy_gettext('Location'), validators=[InputRequired()])
    rating = HiddenField(lazy_gettext('Rating'), default=0)
    notes = TextAreaField(lazy_gettext('Notes'))
    omd_content = TextAreaField(lazy_gettext('OMD Content'), default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%Y-%m-%d')))
    advmode = HiddenField('Advanced Mode', default='false')

class ObservationNewForm(FlaskForm, ObservationMixin):
    submit = SubmitField(lazy_gettext('Add Observation'))

class ObservationEditForm(FlaskForm, ObservationMixin):
    submit = SubmitField(lazy_gettext('Update Observation'))

class AddToObservedListForm(FlaskForm):
    dso_name = StringField(lazy_gettext('DSO name'), validators=[InputRequired(),])
    