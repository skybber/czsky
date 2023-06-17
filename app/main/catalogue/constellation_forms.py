from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    HiddenField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    Length,
)


class SearchConstellationForm(FlaskForm):
    q = StringField(lazy_gettext('Search'))
    season = SelectField(lazy_gettext('Season'), choices=[
        ('All', lazy_gettext('All')),
        ('winter', lazy_gettext('Winter')),
        ('spring', lazy_gettext('Spring')),
        ('summer', lazy_gettext('Summer')),
        ('autumn', lazy_gettext('Autumn')),
        ('southern', lazy_gettext('Southern')),
    ], default=None)


class ConstellationEditForm(FlaskForm):
    common_name = StringField(lazy_gettext('Common Name'), validators=[Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update'))
