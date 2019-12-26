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
    required
)

class SearchDsoForm(FlaskForm):
    q = StringField('Search')
    catalogue = SelectField('Catalogue', choices=[
         ('All', 'All catalogues'),
         ('M', 'Messier'),
         ('NGC', 'NGC'),
         ('IC', 'IC'),
         ('Abell','Abell'),
         ('SH2','Sharpless'),
         ('B', 'Barnard'),
         ('Cr', 'Collinder'),
         ('Pal', 'Palomar'),
         ('PK', 'Perek-Kohoutek'),
         ('Stock', 'Stock'),
         ('UGC', 'UGC'),
         ('Mel', 'Melotte'),
         ('LDN', 'LDN'),
         ('VIC', 'Vic'),
    ])
    dso_type = SelectField('Object type', choices=[
         ('All', 'All types'),
         ('Glx', 'Galaxy'),
         ('GC', 'Globular Cluster'),
         ('OC', 'Open Cluster'),
         ('Neb', 'Nebula'),
         ('PN', 'Planatary Nebula'),
    ])

class DeepskyObjectEditForm(FlaskForm):
    common_name = StringField('Common Name', validators=[Length(max=256)])
    text = TextAreaField('Text')
    submit = SubmitField('Update')

class DeepskyObjectFindChartForm(FlaskForm):
    radius = IntegerField('Field radius', default=2)
    submit = SubmitField('Update')
