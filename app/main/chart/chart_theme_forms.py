
from flask_wtf import FlaskForm
from wtforms.fields import (
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    Length,
)
from flask_babel import lazy_gettext


class ChartThemeEditForm(FlaskForm):
    name = StringField(lazy_gettext('Name'), validators=[Length(max=256)])
    definition = TextAreaField(lazy_gettext('Definition'))
    submit_button = SubmitField(lazy_gettext('Update'))
