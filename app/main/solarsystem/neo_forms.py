from flask_wtf import FlaskForm
from wtforms.fields import BooleanField, FloatField, SelectField
from wtforms.validators import NumberRange, Optional
from flask_babel import lazy_gettext

NEO_DEFAULT_MAGLIM = 16.0


class SearchNeoForm(FlaskForm):
    class Meta:
        csrf = False  # read-only GET filter

    period = SelectField(lazy_gettext('Period'), choices=[
        ('7', lazy_gettext('7 days')),
        ('30', lazy_gettext('30 days')),
        ('60', lazy_gettext('60 days')),
        ('90', lazy_gettext('90 days')),
    ], default='30')
    # Not an empty value: Semantic UI dropdowns treat value="" as a placeholder, not a choice.
    dist_max_ld = SelectField(lazy_gettext('Max. distance'), choices=[
        ('all', lazy_gettext('All')),
        ('1', '1 LD'),
        ('5', '5 LD'),
        ('10', '10 LD'),
        ('25', '25 LD'),
        ('50', '50 LD'),
    ], default='all')
    # Default 16 mag: bright enough to be interesting; up to 18 mag is stored.
    maglim = FloatField(lazy_gettext('Limit mag'), default=NEO_DEFAULT_MAGLIM, validators=[NumberRange(min=-30.0, max=30.0), Optional()])
    pha_only = BooleanField(lazy_gettext('PHA only'), default=False)
