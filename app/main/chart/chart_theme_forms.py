
from flask_wtf import FlaskForm
from wtforms.fields import (
    BooleanField,
    HiddenField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    Length, InputRequired,
)
from flask_babel import lazy_gettext

from app.models import DefaultThemeType
from app.commons.chart_theme_definition import ChartThemeDefinition


class ChartThemeMixin:
    dark_definition = HiddenField()
    light_definition = HiddenField()
    night_definition = HiddenField()
    name = StringField(lazy_gettext('Name'), validators=[InputRequired(), Length(max=256)])
    default_type = SelectField(lazy_gettext('Application theme'), choices=DefaultThemeType.choices(), coerce=DefaultThemeType.coerce, default=DefaultThemeType.DARK)
    definition = TextAreaField(lazy_gettext('Definition'))
    is_active = BooleanField(lazy_gettext('Is active'), default=True)

    def check_definition(self):
        errors = []
        ChartThemeDefinition.create_from_template(self.definition.data, errors)
        if len(errors) > 0:
            for err in errors:
                self.definition.errors.append(err)
            return False
        return True


class ChartThemeNewForm(FlaskForm, ChartThemeMixin):
    submit = SubmitField(lazy_gettext('Add Theme'))

    def validate(self, extra_validators=None):
        if not super(ChartThemeNewForm, self).validate():
            return False
        return self.check_definition()


class ChartThemeEditForm(FlaskForm, ChartThemeMixin):
    submit = SubmitField(lazy_gettext('Update Theme'))

    def validate(self, extra_validators=None):
        if not super(ChartThemeEditForm, self).validate():
            return False
        return self.check_definition()

