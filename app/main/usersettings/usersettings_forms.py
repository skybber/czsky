from flask_wtf import FlaskForm
from wtforms.fields import (
    PasswordField,
    StringField,
    SubmitField,
    TextField,
    TextAreaField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import Email, EqualTo, InputRequired, Length

from flask_babel import lazy_gettext


class PublicProfileForm(FlaskForm):
    user_name = TextField(lazy_gettext('Username'), validators=[InputRequired(), Length(1, 64)], render_kw={'readonly': True})
    full_name = TextField(lazy_gettext('Full Name'), validators=[InputRequired(), Length(1, 256)])
    email = EmailField(lazy_gettext('Email'), validators=[InputRequired(), Length(1, 64), Email()])
    default_country_code = StringField(lazy_gettext('Default country'), validators=[InputRequired(),])
    submit = SubmitField(lazy_gettext('Update'))


class PasswordForm(FlaskForm):
    current_password = PasswordField(lazy_gettext('Current Password'), validators=[InputRequired()])
    new_password = PasswordField( lazy_gettext('New Password'), validators=[InputRequired(), Length(6, 128), EqualTo('new_password2', 'Passwords must match'), ])
    new_password2 = PasswordField(lazy_gettext('Re-Type New Password'), validators=[InputRequired(), Length(6, 128), ])
    submit = SubmitField(lazy_gettext('Update Password'))


class DeleteAccountForm(FlaskForm):
    password = PasswordField(lazy_gettext('Password'), validators=[InputRequired()])
    submit = SubmitField(lazy_gettext('Confirm Deletion'))


class GitSSHKeyForm(FlaskForm):
    git_repository = TextField(lazy_gettext('Git repository'), validators=[Length(1, 512)])
    ssh_public_key = TextAreaField(lazy_gettext('Public key'), render_kw={'readonly': True})
    submit = SubmitField(lazy_gettext('Update'))


class GitContentSSHKeyForm(FlaskForm):
    git_repository = TextField(lazy_gettext('Content git repository'), validators=[Length(1, 512)])
    ssh_public_key = TextAreaField(lazy_gettext('Public key'), render_kw={'readonly': True})
    submit = SubmitField(lazy_gettext('Update'))

