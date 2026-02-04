import re

from flask import url_for, current_app
from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms.fields import (
    BooleanField,
    HiddenField,
    PasswordField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields import EmailField
from wtforms.validators import Email, EqualTo, InputRequired, Length
import requests

from app.models import User


class LoginForm(FlaskForm):
    email = StringField(
        'User name or email', validators=[InputRequired(), Length(1, 64)])
    password = PasswordField('Password', validators=[InputRequired()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log in')

class UserCheck:
    def __init__(self, banned, regex, message=None):
        self.banned = banned
        self.regex = regex

        if not message:
            message = 'Please choose another username'
        self.message = message

    def __call__(self, form, field):
        p = re.compile(self.regex)
        if field.data.lower() in (word.lower() for word in self.banned):
            raise ValidationError(self.message)
        if re.search(p, field.data.lower()):
            raise ValidationError(self.message)

class RegistrationForm(FlaskForm):
    user_name = StringField(
        'User Name', validators=[InputRequired(),
                                 UserCheck(message="Username or special characters not allowed",
                                           banned=['root', 'admin', 'sys', 'administrator'],
                                           regex="^(?=.*[-+!#$%^&*, ?])"),
                                 Length(3, 40)])
    full_name = StringField(
        'Full Name', validators=[InputRequired(),
                                 Length(1, 256)])
    email = EmailField(
        'Email', validators=[InputRequired(),
                             Length(1, 64),
                             Email()])
    password = PasswordField(
        'Password',
        validators=[
            InputRequired(),
            EqualTo('password2', 'Passwords must match')
        ])
    password2 = PasswordField('Confirm password', validators=[InputRequired()])
    cf_turnstile_response = HiddenField('Turnstile Token')
    submit = SubmitField('Register')

    def validate_user_name(self, field):
        if User.query.filter_by(user_name=field.data).first():
            raise ValidationError('User name already registered. (Did you mean to '
                                  '<a href="{}">log in</a> instead?)'.format(
                                    url_for('account.login')))

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered. (Did you mean to '
                                  '<a href="{}">log in</a> instead?)'.format(
                                    url_for('account.login')))

    def validate_cf_turnstile_response(self, field):
        """Validate Turnstile captcha token"""
        secret_key = current_app.config.get('TURNSTILE_SECRET_KEY')
        if not secret_key:
            return  # Skip validation if Turnstile is not configured

        if not field.data:
            raise ValidationError('Please complete the captcha verification.')

        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret_key,
                'response': field.data
            }
        )

        result = response.json()
        if not result.get('success'):
            raise ValidationError('Captcha verification failed. Please try again.')


class RequestResetPasswordForm(FlaskForm):
    email = EmailField(
        'Email', validators=[InputRequired(),
                             Length(1, 64),
                             Email()])
    submit = SubmitField('Reset password')

    # We don't validate the email address so we don't confirm to attackers
    # that an account with the given email exists.


class ResetPasswordForm(FlaskForm):
    email = EmailField(
        'Email', validators=[InputRequired(),
                             Length(1, 64),
                             Email()])
    new_password = PasswordField(
        'New password',
        validators=[
            InputRequired(),
            EqualTo('new_password2', 'Passwords must match.')
        ])
    new_password2 = PasswordField(
        'Confirm new password', validators=[InputRequired()])
    submit = SubmitField('Reset password')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError('Unknown email address.')


class CreatePasswordForm(FlaskForm):
    password = PasswordField(
        'Password',
        validators=[
            InputRequired(),
            EqualTo('password2', 'Passwords must match.')
        ])
    password2 = PasswordField(
        'Confirm new password', validators=[InputRequired()])
    submit = SubmitField('Set password')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old password', validators=[InputRequired()])
    new_password = PasswordField(
        'New password',
        validators=[
            InputRequired(),
            EqualTo('new_password2', 'Passwords must match.')
        ])
    new_password2 = PasswordField(
        'Confirm new password', validators=[InputRequired()])
    submit = SubmitField('Update password')


class ChangeEmailForm(FlaskForm):
    email = EmailField(
        'New email', validators=[InputRequired(),
                                 Length(1, 64),
                                 Email()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Update email')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')
