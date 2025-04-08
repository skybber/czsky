from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    FieldList,
    FormField,
    HiddenField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    InputRequired,
    Length,
)


class UserObjectListItemForm(FlaskForm):
    name = StringField(lazy_gettext('Object Name'), validators=[InputRequired(), Length(max=256), ])
    text = TextAreaField(lazy_gettext('List comment.'), render_kw={'rows': 2})


class UserObjectListItemsEditForm(FlaskForm):
    goback = HiddenField(default='false')
    items = FieldList(FormField(UserObjectListItemForm), min_entries=1)
    submit_button = SubmitField(lazy_gettext('Update Items'))


class UserObjectListMixin:
    title = StringField(lazy_gettext('Title'), validators=[InputRequired(), Length(max=256)])
    text = TextAreaField(lazy_gettext('Text'))
    is_public = BooleanField(lazy_gettext('List is public'), default=False)


class UserObjectListNewForm(FlaskForm, UserObjectListMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Create User Object List'))

    def validate(self, extra_validators=None):
        if not super(UserObjectListNewForm, self).validate():
            return False
        return True


class UserObjectListEditForm(FlaskForm, UserObjectListMixin):
    goback = HiddenField(default='false')
    submit_button = SubmitField(lazy_gettext('Update User Object List'))

    def validate(self, extra_validators=None):
        if not super(UserObjectListEditForm, self).validate():
            return False
        return True
