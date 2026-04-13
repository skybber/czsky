from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms.fields import EmailField
from wtforms.fields import (
    IntegerField,
    PasswordField,
    SubmitField,
    StringField,
    TextAreaField,
)
from wtforms.validators import Email, EqualTo, InputRequired, Length, NumberRange


class PublicProfileForm(FlaskForm):
    user_name = StringField(lazy_gettext('Username'), validators=[InputRequired(), Length(1, 64)], render_kw={'readonly': True})
    full_name = StringField(lazy_gettext('Full Name'), validators=[InputRequired(), Length(1, 256)])
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
    git_repository = StringField(lazy_gettext('Git repository'), validators=[Length(1, 512)])
    ssh_public_key = TextAreaField(lazy_gettext('Public key'), render_kw={'readonly': True})
    submit = SubmitField(lazy_gettext('Update'))


class GitContentSSHKeyForm(FlaskForm):
    git_repository = StringField(lazy_gettext('Content git repository'), validators=[Length(1, 512)])
    ssh_public_key = TextAreaField(lazy_gettext('Public key'), render_kw={'readonly': True})
    submit = SubmitField(lazy_gettext('Update'))


class McpTokenCreateForm(FlaskForm):
    token_name = StringField(
        lazy_gettext('Token name'),
        validators=[InputRequired(), Length(1, 128)],
    )
    current_password = PasswordField(lazy_gettext('Current Password'), validators=[InputRequired()])
    scope = StringField(
        lazy_gettext('Scope'),
        default='wishlist:read wishlist:write sessionplan:read sessionplan:write',
        validators=[InputRequired(), Length(1, 256)],
    )
    expires_in_days = IntegerField(
        lazy_gettext('Expires in days'),
        default=365,
        validators=[InputRequired(), NumberRange(min=1, max=3650)],
    )
    submit = SubmitField(lazy_gettext('Create MCP Token'))


class McpTokenRevokeForm(FlaskForm):
    submit = SubmitField(lazy_gettext('Revoke'))
