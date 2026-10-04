from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    Length, InputRequired,
)
from flask_babel import lazy_gettext


class ChartDrawingEditForm(FlaskForm):
    name = StringField(lazy_gettext('Name'), validators=[InputRequired(), Length(max=128)])
    description = TextAreaField(lazy_gettext('Description'), validators=[Length(max=4000)])
    is_public = BooleanField(lazy_gettext('Public (anyone with the link can view it)'))
    submit = SubmitField(lazy_gettext('Save'))
