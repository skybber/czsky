import calendar
import math

from flask_babel import lazy_gettext as _
from flask_wtf import FlaskForm
from wtforms import DateField, FloatField, IntegerField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, NumberRange, Optional, ValidationError


def finite_number(form, field):
    if field.data is None or not math.isfinite(field.data):
        raise ValidationError(_('Enter a finite number.'))


class DeleteManualCometForm(FlaskForm):
    submit = SubmitField(_('Delete comet'))


class ManualCometForm(FlaskForm):
    designation = StringField(_('Designation'), filters=[lambda value: value.strip() if value else value],
                              validators=[InputRequired(), Length(min=1, max=50)])
    perihelion_year = IntegerField(_('Perihelion year (TT)'), validators=[InputRequired(), NumberRange(min=1, max=9999)])
    perihelion_month = IntegerField(_('Perihelion month'), validators=[InputRequired(), NumberRange(min=1, max=12)])
    perihelion_day = FloatField(_('Perihelion day (including fractional day)'),
                               validators=[InputRequired(), finite_number, NumberRange(min=1, max=32)])
    perihelion_distance_au = FloatField(_('Perihelion distance q (AU)'), validators=[InputRequired(), finite_number])
    eccentricity = FloatField(_('Eccentricity e'), validators=[InputRequired(), finite_number, NumberRange(min=0)])
    inclination_degrees = FloatField(_('Inclination i (degrees)'),
                                    validators=[InputRequired(), finite_number, NumberRange(min=0, max=180)])
    longitude_of_ascending_node_degrees = FloatField(_('Ascending node Ω (degrees)'),
                                                    validators=[InputRequired(), finite_number, NumberRange(min=0, max=360)])
    argument_of_perihelion_degrees = FloatField(_('Argument of perihelion ω (degrees)'),
                                              validators=[InputRequired(), finite_number, NumberRange(min=0, max=360)])
    epoch = DateField(_('Epoch of elements (TT, YYYY-MM-DD)'), validators=[InputRequired()])
    magnitude_g = FloatField(_('Absolute magnitude H'), validators=[Optional(), finite_number])
    magnitude_k = FloatField(_('Brightness slope k'), validators=[Optional(), finite_number])
    reference = StringField(_('Source / reference'), validators=[Optional(), Length(max=30)])
    submit = SubmitField(_('Save comet'))

    def validate_perihelion_distance_au(self, field):
        if field.data is not None and field.data <= 0:
            raise ValidationError(_('Perihelion distance must be positive.'))

    def validate_perihelion_day(self, field):
        year, month, day = self.perihelion_year.data, self.perihelion_month.data, field.data
        if year and month and 1 <= month <= 12 and day is not None and math.isfinite(day):
            if not 1 <= day < calendar.monthrange(year, month)[1] + 1:
                raise ValidationError(_('Invalid perihelion date.'))

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        if (self.magnitude_g.data is None) != (self.magnitude_k.data is None):
            self.magnitude_g.errors.append(_('Provide both brightness parameters, or leave both empty.'))
            valid = False
        return valid
