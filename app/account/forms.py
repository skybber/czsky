import re
import requests

from flask import current_app, request, url_for
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

from app.models import User


# -----------------------------
# Turnstile verification (top of file)
# -----------------------------

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _turnstile_enabled() -> bool:
    """Return True if Turnstile is configured."""
    return bool(current_app.config.get("TURNSTILE_SECRET_KEY"))


def verify_turnstile_token(token: str, remoteip: str | None = None) -> dict:
    """
    Verify a Turnstile token via Cloudflare siteverify API.

    Returns JSON dict (including 'success').
    Raises requests.RequestException for network/HTTP errors.
    """
    secret = current_app.config.get("TURNSTILE_SECRET_KEY")
    data = {"secret": secret, "response": token}
    if remoteip:
        data["remoteip"] = remoteip

    resp = requests.post(TURNSTILE_VERIFY_URL, data=data, timeout=5)
    resp.raise_for_status()
    result = resp.json()

    # Optional hardening checks
    expected_hosts = current_app.config.get("TURNSTILE_EXPECTED_HOSTNAMES")
    if expected_hosts:
        actual = result.get("hostname")
        if actual not in expected_hosts:
            result["success"] = False
            result.setdefault("error-codes", []).append("bad-hostname")

    # expected_action = current_app.config.get("TURNSTILE_EXPECTED_ACTION")
    # # Only useful if you use data-action on the widget
    # if expected_action and result.get("action") != expected_action:
    #     result["success"] = False
    #     result.setdefault("error-codes", []).append("bad-action")

    return result


# -----------------------------
# Turnstile validation mixin
# -----------------------------


class TurnstileMixin:
    """Mixin to add Turnstile validation to any FlaskForm."""

    def validate_turnstile(self):
        """
        Validate Turnstile token from request.
        Returns True if valid, False otherwise (with errors attached to cf_turnstile field).
        """
        if not _turnstile_enabled():
            if current_app.debug:
                return True
            self.cf_turnstile.errors.append("Captcha is not configured on the server.")
            return False

        token = (request.form.get("cf-turnstile-response") or "").strip()

        if not token:
            self.cf_turnstile.errors.append("Please complete the captcha verification.")
            return False

        try:
            result = verify_turnstile_token(token, remoteip=request.remote_addr)
        except requests.RequestException:
            self.cf_turnstile.errors.append(
                "Captcha verification is temporarily unavailable. Please try again."
            )
            return False

        if not result.get("success"):
            self.cf_turnstile.errors.append("Captcha verification failed. Please try again.")
            return False

        self.cf_turnstile.data = token
        return True


# -----------------------------
# Existing forms
# -----------------------------

class LoginForm(FlaskForm):
    email = StringField("User name or email", validators=[InputRequired(), Length(1, 64)])
    password = PasswordField("Password", validators=[InputRequired()])
    remember_me = BooleanField("Keep me logged in")
    submit = SubmitField("Log in")


class UserCheck:
    def __init__(self, banned, regex, message=None):
        self.banned = banned
        self.regex = regex

        if not message:
            message = "Please choose another username"
        self.message = message

    def __call__(self, form, field):
        p = re.compile(self.regex)
        if field.data.lower() in (word.lower() for word in self.banned):
            raise ValidationError(self.message)
        if re.search(p, field.data.lower()):
            raise ValidationError(self.message)


class RegistrationForm(TurnstileMixin, FlaskForm):
    user_name = StringField(
        "User Name",
        validators=[
            InputRequired(),
            UserCheck(
                message="Username or special characters not allowed",
                banned=["root", "admin", "sys", "administrator"],
                regex=r"^(?=.*[-+!#$%^&*, ?])",
            ),
            Length(3, 40),
        ],
    )
    full_name = StringField("Full Name", validators=[InputRequired(), Length(1, 256)])
    email = EmailField("Email", validators=[InputRequired(), Length(1, 64), Email()])
    password = PasswordField(
        "Password",
        validators=[
            InputRequired(),
            EqualTo("password2", "Passwords must match"),
        ],
    )
    password2 = PasswordField("Confirm password", validators=[InputRequired()])

    # NOTE: Turnstile posts token as "cf-turnstile-response".
    # We keep this field only to store/show errors in WTForms cleanly.
    cf_turnstile = HiddenField("Turnstile")

    submit = SubmitField("Register")

    def validate_user_name(self, field):
        if User.query.filter_by(user_name=field.data).first():
            raise ValidationError(
                'User name already registered. (Did you mean to <a href="{}">log in</a> instead?)'.format(
                    url_for("account.login")
                )
            )

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError(
                'Email already registered. (Did you mean to <a href="{}">log in</a> instead?)'.format(
                    url_for("account.login")
                )
            )

    def validate(self, extra_validators=None):
        """Extend base validation with Turnstile verification."""
        if not super().validate(extra_validators=extra_validators):
            return False
        return self.validate_turnstile()


class RequestResetPasswordForm(TurnstileMixin, FlaskForm):
    email = EmailField("Email", validators=[InputRequired(), Length(1, 64), Email()])
    cf_turnstile = HiddenField("Turnstile")
    submit = SubmitField("Reset password")
    # We don't validate the email address so we don't confirm to attackers
    # that an account with the given email exists.

    def validate(self, extra_validators=None):
        """Extend base validation with Turnstile verification."""
        if not super().validate(extra_validators=extra_validators):
            return False
        return self.validate_turnstile()


class ResetPasswordForm(FlaskForm):
    email = EmailField("Email", validators=[InputRequired(), Length(1, 64), Email()])
    new_password = PasswordField(
        "New password",
        validators=[
            InputRequired(),
            EqualTo("new_password2", "Passwords must match."),
        ],
    )
    new_password2 = PasswordField("Confirm new password", validators=[InputRequired()])
    submit = SubmitField("Reset password")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError("Unknown email address.")


class CreatePasswordForm(FlaskForm):
    password = PasswordField(
        "Password",
        validators=[
            InputRequired(),
            EqualTo("password2", "Passwords must match."),
        ],
    )
    password2 = PasswordField("Confirm new password", validators=[InputRequired()])
    submit = SubmitField("Set password")


class ChangePasswordForm(TurnstileMixin, FlaskForm):
    old_password = PasswordField("Old password", validators=[InputRequired()])
    new_password = PasswordField(
        "New password",
        validators=[
            InputRequired(),
            EqualTo("new_password2", "Passwords must match."),
        ],
    )
    new_password2 = PasswordField("Confirm new password", validators=[InputRequired()])
    cf_turnstile = HiddenField("Turnstile")
    submit = SubmitField("Update password")

    def validate(self, extra_validators=None):
        """Extend base validation with Turnstile verification."""
        if not super().validate(extra_validators=extra_validators):
            return False
        return self.validate_turnstile()


class ChangeEmailForm(TurnstileMixin, FlaskForm):
    email = EmailField("New email", validators=[InputRequired(), Length(1, 64), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    cf_turnstile = HiddenField("Turnstile")
    submit = SubmitField("Update email")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("Email already registered.")

    def validate(self, extra_validators=None):
        """Extend base validation with Turnstile verification."""
        if not super().validate(extra_validators=extra_validators):
            return False
        return self.validate_turnstile()
