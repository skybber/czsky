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

from app.models import DeepskyObject
from app.commons.dso_utils import normalize_dso_name

DEFAULT_OBSERVATION_CONTENT = '''
## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(22:30):
Observation item1 notes
'''

class ObservationItemNewForm(FlaskForm):
    deepsky_object_id_list = StringField('DSO list optionally with comment. (e.g. M3,M5:nice globulars!)')
    date_time = TimeField('Time', format = '%H:%M', default = datetime.now().time())
    notes = TextAreaField('Notes', render_kw={'rows':2})

    def validate_deepsky_object_id_list(form, field):
        if field.id != 'items-0-deepsky_object_id_list':
            dsos = field.data
            if ':' in dsos:
                dsos = dsos[:dsos.index(':')]
            if len(dsos) == 0:
                raise ValidationError("Value expected.")
            for dso_name in dsos.split(','):
                dso_name = normalize_dso_name(dso_name)
                dso = DeepskyObject.query.filter_by(name=dso_name).first()
                if not dso:
                    raise ValidationError("DSO not found. Dso name:" + dso_name)

    def validate_date_time(form, field):
        if field.id != 'items-0-date_time':
            if not field.data:
                raise ValidationError("Value expected.")


class ObservationMixin():
    items = FieldList(FormField(ObservationItemNewForm), min_entries = 1)
    title = StringField('Title', validators=[InputRequired(), Length(max=256),])
    date = DateField('Date', id='odate', format = '%d/%m/%Y', default = datetime.today, validators=[InputRequired(),])
    location_id = IntegerField('Location', validators=[InputRequired()])
    rating = HiddenField('Rating', default=0)
    notes = TextAreaField('Notes')
    omd_content = TextAreaField('OMD Content', default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%Y-%m-%d')))
    advmode = HiddenField('Advanced Mode', default='false')

class ObservationNewForm(FlaskForm, ObservationMixin):
    submit = SubmitField('Add Observation')

class ObservationEditForm(FlaskForm, ObservationMixin):
    submit = SubmitField('Update Observation')
