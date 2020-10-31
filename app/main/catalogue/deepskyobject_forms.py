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
         ('Sh2','Sharpless'),
         ('HCG', 'Hickson'),
         ('B', 'Barnard'),
         ('Cr', 'Collinder'),
         ('Pal', 'Palomar'),
         ('PK', 'Perek-Kohoutek'),
         ('Stock', 'Stock'),
         ('UGC', 'UGC'),
         ('Mel', 'Melotte'),
         ('LDN', 'LDN'),
         ('VIC', 'Vic'),
    ], default='')
    dso_type = SelectField('Object type', choices=[
         ('All', 'All types'),
         ('GX', 'Galaxy'),
         ('GC', 'Globular Cluster'),
         ('OC', 'Open Cluster'),
         ('BN', 'Nebula'),
         ('PN', 'Planetary Nebula'),
    ], default='')
    maglim = IntegerField(lazy_gettext('Limit mag'), default=12)

class DsoApertureDescriptionForm(FlaskForm):
    aperture_class = HiddenField()
    text = TextAreaField(render_kw={'rows':3})
    is_public = BooleanField('Public')

class DeepskyObjectEditForm(FlaskForm):
    common_name = StringField(lazy_gettext('Common Name'), validators=[Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    references = TextAreaField(lazy_gettext('References'), render_kw={'rows':2})
    rating = HiddenField(lazy_gettext('Rating'), default=1)
    aperture_descr_items = FieldList(FormField(DsoApertureDescriptionForm))
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update'))

class DeepskyObjectFindChartForm(FlaskForm):
    radius = IntegerField(lazy_gettext('Field radius'), default=8, validators=[Length(min=1, max=8)])
    maglim = IntegerField(lazy_gettext('Limit mag'), default=7)
    dso_maglim = IntegerField(lazy_gettext('DSO limit mag'), default=8)
    mirror_x = BooleanField(lazy_gettext('Mirror X'), default=False)
    mirror_y = BooleanField(lazy_gettext('Mirror Y'), default=False)
    ra = HiddenField('ra')
    dec = HiddenField('dec')
    fullscreen = HiddenField('fullscreen')
