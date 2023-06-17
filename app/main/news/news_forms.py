from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    IntegerField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    Length,
    NumberRange,
)

from app.commons.coordinates import radec_check


class NewsMixin:
    title = StringField(lazy_gettext('Title'), validators=[Length(max=128)])
    title_row = StringField(lazy_gettext('Title row'), validators=[Length(max=1024)])
    radec = StringField(lazy_gettext('Coordinates'), validators=[Length(max=256), radec_check])
    text = TextAreaField(lazy_gettext('text'))
    rating = IntegerField(lazy_gettext('Rating'), default=5, validators=[NumberRange(min=0, max=10)])
    is_released = BooleanField(lazy_gettext('Is released'), default=False)


class NewsNewForm(FlaskForm, NewsMixin):
    submit = SubmitField(lazy_gettext('Add news'))


class NewsEditForm(FlaskForm, NewsMixin):
    submit = SubmitField(lazy_gettext('Update news'))


class SearchNewsForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    items_per_page = IntegerField(lazy_gettext('Items per page'))