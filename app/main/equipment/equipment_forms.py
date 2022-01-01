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

from app.commons.coordinates import lonlat_check

from app.models import TelescopeType, FilterType, LensType

BARREL_DIAMETERS_CHOICES = [(d, str(d) + '"') for d in [0.965, 1.25, 2, 2.7, 3, 4]]


class TelescopeMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    telescope_type = SelectField(lazy_gettext('Telescope Type'), choices=TelescopeType.choices(), coerce=TelescopeType.coerce, default=TelescopeType.REFRACTOR)
    aperture_mm = IntegerField(lazy_gettext('Aperture (mm)'), validators=[NumberRange(min=1, max=100000)])
    focal_length_mm = IntegerField(lazy_gettext('Focal Length (mm)'), validators=[NumberRange(min=1, max=100000), Optional()])
    fixed_magnification = FloatField(lazy_gettext('Fixed magnification'), validators=[NumberRange(min=0.1, max=10000.0), Optional()])
    is_default = BooleanField(lazy_gettext('Is default'), default=False)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)

    def validate_foc_len_fix_mag(self):
        if self.focal_length_mm.data is None and self.fixed_magnification.data is None:
            msg = lazy_gettext('At least one of "Focal Length" or "Fixed Magnification" must be set')
            self.focal_length_mm.errors.append(msg)
            self.fixed_magnification.errors.append(msg)
            return False
        return True


class TelescopeNewForm(FlaskForm, TelescopeMixin):
    submit = SubmitField(lazy_gettext('Add Telescope'))

    def validate(self):
        if not super(TelescopeNewForm, self).validate():
            return False
        return self.validate_foc_len_fix_mag()


class TelescopeEditForm(FlaskForm, TelescopeMixin):
    submit = SubmitField(lazy_gettext('Update Telescope'))

    def validate(self):
        if not super(TelescopeEditForm, self).validate():
            return False
        return self.validate_foc_len_fix_mag()


class EyepieceMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[Length(max=128)])
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
    vendor = StringField(lazy_gettext('Vendor'), validators=[Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    filter_type = SelectField(lazy_gettext('Filter Type'), choices=FilterType.choices(), coerce=FilterType.coerce, default=FilterType.UHC)
    diameter_inch = SelectField(lazy_gettext('Diameter (inch)'), choices=BARREL_DIAMETERS_CHOICES, coerce=float)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)


class FilterNewForm(FlaskForm, FilterMixin):
    submit = SubmitField(lazy_gettext('Add Filter'))


class FilterEditForm(FlaskForm, FilterMixin):
    submit = SubmitField(lazy_gettext('Update Filter'))


class LensMixin:
    name = StringField(lazy_gettext('Name'), validators=[Length(max=128)])
    vendor = StringField(lazy_gettext('Vendor'), validators=[Length(max=128)])
    model = StringField(lazy_gettext('Model'), validators=[InputRequired(), Length(max=128)])
    descr = TextAreaField(lazy_gettext('Notes'))
    lens_type = SelectField(lazy_gettext('Lens Type'), choices=LensType.choices(), coerce=LensType.coerce, default=LensType.BARLOW)
    magnification = FloatField(lazy_gettext('Magnification'), validators=[NumberRange(min=0.1, max=10000.0)])
    diameter_inch = SelectField(lazy_gettext('Diameter (inch)'), choices=BARREL_DIAMETERS_CHOICES, coerce=float)
    is_active = BooleanField(lazy_gettext('Is active'), default=True)


class LensNewForm(FlaskForm, LensMixin):
    submit = SubmitField(lazy_gettext('Add Lens'))


class LensEditForm(FlaskForm, LensMixin):
    submit = SubmitField(lazy_gettext('Update Lens'))

