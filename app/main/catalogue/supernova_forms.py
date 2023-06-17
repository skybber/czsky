from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    FloatField,
    IntegerField,
    StringField,
)


class SearchSupernovaForm(FlaskForm):
    q = StringField('Search')
    latest_mag_max = FloatField(lazy_gettext('Latest mag max'), default=18.0)
    dec_min = FloatField(lazy_gettext('Dec min'), default=-35.0)
    constellation_id = IntegerField('Constellation', default=None)
    items_per_page = IntegerField(lazy_gettext('Items per page'))

