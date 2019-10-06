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

class SearchForm(FlaskForm):
    q = StringField('Search')

class SearchDsoForm(FlaskForm):
    q = StringField('Search')
    catalogue = SelectField('Catalogue', choices=[
         ('All', 'All'),
         ('M', 'Messier'),
         ('NGC', 'Ngc'),
         ('IC', 'IC'),
         ('ABELL','Abell'),
         ('VIC','Vic'),
    ])
    dso_type = SelectField('Object type', choices=[
         ('All', 'All'),
         ('G', 'Galaxy'),
         ('GCl', 'Globular Cluster'),
         ('OCl', 'Open Cluster'),
         ('Neb', 'Nebula'),
         ('PN', 'Planatary Nebula'),
    ])

class ObservationItemNewForm(FlaskForm):
    deep_sky_object_id_list = StringField('Deepsky object list (separated by \';\')', validators=[required()])
    date_time = TimeField('Time', format = '%H:%M', default = datetime.now())
    notes = TextAreaField('Notes', render_kw={'rows':2})

class ObservationNewForm(FlaskForm):
    items = FieldList(FormField(ObservationItemNewForm), min_entries = 1)
    date = DateField('Date', id='odate', format = '%d/%m/%Y', default = datetime.now())
    notes = TextAreaField('Notes', render_kw={'rows':3})
    rating = HiddenField('Rating', default=1)
    submit = SubmitField('Add')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    notes = StringField('First name', validators=[Length(max=5000)])
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Update')

class LocationNewForm(FlaskForm):
    name = StringField('Name', validators=[Length(max=128)])
    longitude = StringField('Longitude', validators=[Length(max=128)])
    latitude = StringField('Latitude', validators=[Length(max=128)])
    descr = TextAreaField('Notes')
    bortle = FloatField('Bortle', validators=[NumberRange(min=0.0, max=9.0)])
    is_public = BooleanField('Is public')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Add')

class LocationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    notes = TextAreaField('Notes')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    submit = SubmitField('Update')
