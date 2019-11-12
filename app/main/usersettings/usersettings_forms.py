from flask import url_for
from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    PasswordField,
    StringField,
    SubmitField,
    TextField,
    TextAreaField,
)
from wtforms.fields.html5 import EmailField
from wtforms.validators import Email, EqualTo, InputRequired, Length

from app.models import User

class PublicProfileForm(FlaskForm):
    user_name = TextField('Username', validators=[InputRequired(), Length(1, 64)], render_kw={'readonly': True})
    full_name = TextField('Full Name', validators=[InputRequired(), Length(1, 256)])
    email = EmailField('Email', validators=[InputRequired(), Length(1, 64), Email()])
    submit = SubmitField('Update')

class PasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[InputRequired()])
    new_password = PasswordField( 'New Password', validators=[InputRequired(), Length(6, 128), EqualTo('new_password2', 'Passwords must match'), ])
    new_password2 = PasswordField('Re-Type New Password', validators=[InputRequired(), Length(6, 128), ])
    submit = SubmitField('Update Password')

class DeleteAccountForm(FlaskForm):
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Confirm Deletion')

class SSHKeyForm(FlaskForm):
    ssh_public_key = TextAreaField('Public key')