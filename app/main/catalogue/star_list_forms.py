from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import (
    SelectField,
)


class SearchStarListForm(FlaskForm):
    season = SelectField(lazy_gettext('Season'), choices=[
         ('All', lazy_gettext('All')),
         ('winter', lazy_gettext('Winter')),
         ('spring', lazy_gettext('Spring')),
         ('summer', lazy_gettext('Summer')),
         ('autumn', lazy_gettext('Autumn')),
         ('southern', lazy_gettext('Southern')),
    ], default='')