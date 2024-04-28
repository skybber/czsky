from flask import (
    current_app,
    request,
)

from app.models.user import User
from flask_babel import gettext


def to_int(value, default):
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return default


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


def get_anonymous_user():
    return User.query.filter_by(user_name=current_app.config.get('ANONYMOUS_USER_NAME')).first()


def get_cs_editor_user():
    return User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_CS')).first()


def get_lang_and_editor_user_from_request(for_constell_descr=False):
    # supported_languages = ["cs", "en"]
    # lang = werkzeug.datastructures.LanguageAccept([(al[0][0:2], al[1]) for al in request.accept_languages]).best_match(supported_languages)
    # return lang, User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + lang.upper())).first()
    host = request.headers.get('Host')
    lang = 'en' if host and 'czsky.eu' in host else 'cs'
    editor_env_lang = lang
    if for_constell_descr:
        editor_env_lang = 'cs'
    return lang, User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + editor_env_lang.upper())).first()


def get_lang_and_all_editor_users_from_request(for_constell_descr=False):
    # supported_languages = ["cs", "en"]
    # lang = werkzeug.datastructures.LanguageAccept([(al[0][0:2], al[1]) for al in request.accept_languages]).best_match(supported_languages)
    # return lang, User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + lang.upper())).first()
    host = request.headers.get('Host')
    lang = 'en' if host and 'czsky.eu' in host else 'cs'
    editor_env_lang = lang
    if for_constell_descr:
        editor_env_lang = 'cs'
    str_all_editors = current_app.config.get('ALL_EDITORS_USER_NAMES_' + editor_env_lang.upper())
    if str_all_editors:
        all_editors_ar = [x.strip() for x in str_all_editors.split(',')]
        all_editors = User.query.filter(User.user_name.in_(all_editors_ar)).all()
    else:
        editor = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_' + editor_env_lang.upper())).first()
        all_editors = ( editor, )
    return lang, all_editors


def get_site_lang_code():
    host = request.headers.get('Host')
    return 'en' if host and 'czsky.eu' in host else 'cs'

def is_splitview_supported():
    screenWidth = request.args.get("screenWidth")
    if screenWidth:
        try:
            screenWidth = int(screenWidth)
            return screenWidth > 768
        except ValueError:
            pass
    return False

def get_about_oal():
    return gettext("""
## Goal
**OpenAstronomyLog** is a free and open XML schema definition for all kinds of astronomical observations. 
Software that supports this schema enables an observer to share observations with other observers or move observations 
among software products.

## History
The schema (formerly known as COMAST schema) was primarily developed by the 
german ["Fachgruppe für Computerastronomie"](http://www.vds-astro.de/fachgruppen/computerastronomie.html) (section for computerastronomy) which is a subsection of Germany's largest
astronomy union, [VDS](http://www.vds-astro.de/) (Vereinigung der Sternfreunde e.V.) 
Starting with version 2.0 the schema was renamed from COMAST (abbr. for *Com*puter *Ast*ronomy) to **OpenAstronomyLog**, or **\<OAL\>**.

## Documentation
Please see our [wiki section](https://github.com/openastronomylog/openastronomylog/wiki) as well as the [doc](https://github.com/openastronomylog/openastronomylog/tree/master/doc) folder

## License
The schema is released under the [APACHE Software License 2.0](https://github.com/openastronomylog/openastronomylog/blob/master/LICENSE) and is currently supported in both open source and 
commercial software. Just [download the schema archive](https://github.com/openastronomylog/openastronomylog/blob/master/OAL21.zip?raw=true)!

## Contribution
In you want to contribute to **\<OAL\>** please join the [OpenAstronomyLog discussion group](https://groups.google.com/forum/#!forum/openastronomylog).
""")
