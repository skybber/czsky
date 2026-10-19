from flask_wtf import FlaskForm
from wtforms.fields import BooleanField, FloatField, SelectField
from wtforms.validators import NumberRange, Optional
from flask_babel import lazy_gettext


class SearchNeoForm(FlaskForm):
    class Meta:
        csrf = False  # read-only GET filter

    period = SelectField(lazy_gettext('Period'), choices=[
        ('7', lazy_gettext('7 days')),
        ('30', lazy_gettext('30 days')),
        ('60', lazy_gettext('60 days')),
    ], default='30')
    dist_max_ld = SelectField(lazy_gettext('Max. distance'), choices=[
        ('', lazy_gettext('All')),
        ('1', '1 LD'),
        ('5', '5 LD'),
        ('10', '10 LD'),
    ], default='')
    maglim = FloatField(lazy_gettext('Limit mag'), default=None, validators=[NumberRange(min=-30.0, max=30.0), Optional()])
    pha_only = BooleanField(lazy_gettext('PHA only'), default=False)
