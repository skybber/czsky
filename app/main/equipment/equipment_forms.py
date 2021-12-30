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

from app.commons.coordinates import lonlat_check

from app.models import TelescopeType, FilterType

BARREL_DIAMETERS_CHOICES = [(d, str(d) + '"') for d in [0.965, 1.25, 2, 2.7, 3, 4]]


class TelescopeMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[InputRequired(), Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    telescope_type = SelectField(lazy_gettext('Telescope Type'), choices=TelescopeType.choices(), coerce=TelescopeType.coerce, default=TelescopeType.REFRACTOR)
    aperture_mm = IntegerField(lazy_gettext('Aperture (mm)'), validators=[NumberRange(min=1, max=100000)])
    focal_length_mm = IntegerField(lazy_gettext('Focal Length (mm)'), validators=[NumberRange(min=1, max=100000)])
    is_default = BooleanField(lazy_gettext('Is default'), default=False)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)


class TelescopeNewForm(FlaskForm, TelescopeMixin):
    submit = SubmitField(lazy_gettext('Add Telescope'))


class TelescopeEditForm(FlaskForm, TelescopeMixin):
    submit = SubmitField(lazy_gettext('Update Telescope'))


class EyepieceMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[InputRequired(), Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    focal_length_mm = FloatField(lazy_gettext('Focal Length (mm)'), validators=[NumberRange(min=0.0, max=1000.0)])
    fov_deg = IntegerField(lazy_gettext('Field of view (deg)'), validators=[NumberRange(min=1, max=180)])
    diameter_inch = SelectField(lazy_gettext('Diameter (inch)'), choices=BARREL_DIAMETERS_CHOICES, coerce=float)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)


class EyepieceNewForm(FlaskForm, EyepieceMixin):
    submit = SubmitField(lazy_gettext('Add Eyepiece'))


class EyepieceEditForm(FlaskForm, EyepieceMixin):
    submit = SubmitField(lazy_gettext('Update Eyepiece'))


class FilterMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[InputRequired(), Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    filter_type = SelectField(lazy_gettext('Filter Type'), choices=FilterType.choices(), coerce=FilterType.coerce, default=FilterType.UHC)
    diameter_inch = SelectField(lazy_gettext('Diameter (inch)'), choices=BARREL_DIAMETERS_CHOICES, coerce=float)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)


class FilterNewForm(FlaskForm, FilterMixin):
    submit = SubmitField(lazy_gettext('Add Filter'))


class FilterEditForm(FlaskForm, FilterMixin):
    submit = SubmitField(lazy_gettext('Update Filter'))

