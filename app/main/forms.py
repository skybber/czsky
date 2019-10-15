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

class SearchConstellationForm(FlaskForm):
    q = StringField('Search')
    season = SelectField('Season', choices=[
         ('All', 'All'),
         ('winter', 'Winter'),
         ('spring', 'Spring'),
         ('summer', 'Summer'),
         ('autumn','Autumn'),
         ('southern','Southern'),
    ])

class SearchDsoForm(FlaskForm):
    q = StringField('Search')
    catalogue = SelectField('Catalogue', choices=[
         ('All', 'All catalogues'),
         ('M', 'Messier'),
         ('NGC', 'NGC'),
         ('IC', 'IC'),
         ('Abell','Abell'),
         ('SH2','Sharpless'),
         ('VIC','Vic'),
    ])
    dso_type = SelectField('Object type', choices=[
         ('All', 'All types'),
         ('G', 'Galaxy'),
         ('GCl', 'Globular Cluster'),
         ('OCl', 'Open Cluster'),
         ('Neb', 'Nebula'),
         ('PN', 'Planatary Nebula'),
    ])

DEFAULT_OBSERVATION_CONTENT = '''
# Observation name
:location: location_name
:date: {date}
:observers: @user1, @user2 ...
:seeing: seeing scale
:sqm_1:T(time): 21.30, 21.35

general observation description, use:
* @user to reference observer
* @user:inventory_name to reference user inventory
* @user:observation to reference user observation
* #dso_name to reference dso e.g. #ngc7000
* #location to reference specific location

## NGC891:T(21:30):
Observation item1 notes

## NGC7008,NGC7048:T(21:30):
Observation item1 notes
'''

class ObservationItemNewForm(FlaskForm):
    deep_sky_object_id_list = StringField('Deepsky object list (separated by \';\')', validators=[required()])
    date_time = TimeField('Time', format = '%H:%M', default = datetime.now())
    notes = TextAreaField('Notes', render_kw={'rows':2})

class ObservationNewForm(FlaskForm):
    date = DateField('Date', id='odate', format = '%d/%m/%Y', default = datetime.now())
    rating = HiddenField('Rating', default=1)
    omd_content = TextAreaField('OMD Content',
                                default=DEFAULT_OBSERVATION_CONTENT.format(date=datetime.now().strftime('%d/%m/%Y')),
                                validators=[required()]
                                )
    submit = SubmitField('Add')

class ObservationEditForm(FlaskForm):
    date = DateField('Date', id='datepick')
    rating = IntegerField('Rating', validators=[NumberRange(min=0, max=10)])
    omd_content = TextAreaField('OMD Content')
    submit = SubmitField('Update')

class ConstellationEditForm(FlaskForm):
    common_name = StringField('Common Name', validators=[Length(max=256)])
    text = TextAreaField('Text')
    submit = SubmitField('Update')

class DeepskyObjectEditForm(FlaskForm):
    common_name = StringField('Common Name', validators=[Length(max=256)])
    text = TextAreaField('Text')
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
