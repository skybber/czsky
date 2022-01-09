from flask_wtf import FlaskForm

from wtforms.fields import (
    IntegerField,
    StringField,
)

from flask_babel import lazy_gettext


class SearchImportHistoryRecsForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    items_per_page = IntegerField(lazy_gettext('Items per page'))
