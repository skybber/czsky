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
from flask_babel import lazy_gettext

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
    common_name = StringField(lazy_gettext('Common Name'), validators=[Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    submit = SubmitField(lazy_gettext('Update'))

class DeepskyObjectFindChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=2, validators=[Length(min=1, max=3)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=10)
    mirror_x = BooleanField(lazy_gettext('Mirror X'), default=False)
    mirror_y = BooleanField(lazy_gettext('Mirror Y'), default=False)
    submit = SubmitField(lazy_gettext('Update'))
