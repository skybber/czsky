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
    required
)
from flask_babel import lazy_gettext


class SearchDsoForm(FlaskForm):
    q = StringField('Search')
    catalogue = SelectField(lazy_gettext('Catalogue'), choices=[
         ('All', lazy_gettext('All catalogues')),
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
    ], default='All')
    dso_type = SelectField(lazy_gettext('Object type'), choices=[
         ('All', lazy_gettext('All types')),
         ('GX', 'Galaxy'),
         ('GC', 'Globular Cluster'),
         ('OC', 'Open Cluster'),
         ('BN', 'Nebula'),
         ('PN', 'Planetary Nebula'),
    ], default='All')
    maglim = FloatField(lazy_gettext('Limit mag'), default=12.0, validators=[NumberRange(min=-30.0, max=30.0), Optional()])
    constellation_id = IntegerField('Constellation', default=None)
    dec_min = FloatField(lazy_gettext('Dec min'), default=-35.0, validators=[NumberRange(min=-90.0, max=90.0), Optional()])
    max_axis_ratio = FloatField(lazy_gettext('Max axis ratio'), default=None, validators=[NumberRange(min=0.0, max=1.0), Optional()])
    items_per_page = IntegerField(lazy_gettext('Items per page'))


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


class DeepskyObjectObservationLog(FlaskForm):
    notes = TextAreaField(lazy_gettext('Notes'))
    submit = SubmitField(lazy_gettext('Update'))
