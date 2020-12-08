import werkzeug

from flask import (
    current_app,
    request,
)

from werkzeug.datastructures import LanguageAccept

from app.models.user import User

def to_float(value, default):
    if value is not None:
        try:
            return float(value)
        except ValueError:
            pass
    return default

def to_boolean(value, default):
    if value is not None:
        if value == '0' or value == 'False':
            return False
        return True
    return default


def get_lang_and_editor_user_from_request():
    # supported_languages = ["cs", "en"]
    # lang = werkzeug.datastructures.LanguageAccept([(al[0][0:2], al[1]) for al in request.accept_languages]).best_match(supported_languages)
    # return lang, User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + lang.upper())).first()
    host = request.headers.get('Host')
    lang = 'en' if host and 'czsky.eu' in host else 'cs'
    return lang, User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + lang.upper())).first()