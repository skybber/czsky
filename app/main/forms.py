from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    IntegerField,
    StringField,
)


class SearchForm(FlaskForm):
    q = StringField('Search')
    items_per_page = IntegerField(lazy_gettext('Items per page'))

