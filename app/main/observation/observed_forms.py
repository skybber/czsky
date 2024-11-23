from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    IntegerField,
    StringField,
)
from wtforms.validators import (
    InputRequired,
)


class AddToObservedListForm(FlaskForm):
    object_name = StringField(lazy_gettext('Object identification'), validators=[InputRequired(),])


class SearchObservedForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    items_per_page = IntegerField(lazy_gettext('Items per page'))
