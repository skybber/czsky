from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import SubmitField


class OAuthConsentForm(FlaskForm):
    allow = SubmitField(lazy_gettext('Allow'))
    deny = SubmitField(lazy_gettext('Deny'))
