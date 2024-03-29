from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    FloatField,
    SelectField,
    StringField,
)


class SearchDoubleStarListForm(FlaskForm):
    q = StringField('Search')
    season = SelectField(lazy_gettext('Season'), choices=[
        ('All', lazy_gettext('All')),
        ('winter', lazy_gettext('Winter')),
        ('spring', lazy_gettext('Spring')),
        ('summer', lazy_gettext('Summer')),
        ('autumn', lazy_gettext('Autumn')),
        ('southern', lazy_gettext('Southern')),
    ], default='')
    mag_max = FloatField(lazy_gettext('Mag max'), default=12.0)
    delta_mag_min = FloatField(lazy_gettext('Delta mag min'), default=0.0)
    delta_mag_max = FloatField(lazy_gettext('Delta mag max'), default=20.0)
    separation_min = FloatField(lazy_gettext('Separation min'), default=1.0)
    separation_max = FloatField(lazy_gettext('Separation max'), default=60.0)
    dec_min = FloatField(lazy_gettext('Dec min'), default=-35.0)

