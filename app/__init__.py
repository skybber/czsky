import os

from flask import (
    Flask,
    request,
    current_app,
)
from flask_assets import Environment
from flask_compress import Compress
from flask_login import LoginManager
from flask_mail import Mail
from flask_rq import RQ
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_babel import Babel

from app.assets import app_css, app_js, vendor_css, vendor_js, default_theme_css, dark_theme_css
from config import config as Config

basedir = os.path.abspath(os.path.dirname(__file__))

mail = Mail()
db = SQLAlchemy()
csrf = CSRFProtect()
compress = Compress()
babel = Babel()

# Set up Flask-Login
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'account.login'


def create_app(config):
    app = Flask(__name__)
    config_name = config

    if not isinstance(config, str):
        config_name = os.getenv('FLASK_CONFIG', 'default')

    app.config.from_object(Config[config_name])
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # not using sqlalchemy event system, hence disabling it

    Config[config_name].init_app(app)

    # Set up extensions
    mail.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    compress.init_app(app)
    babel.init_app(app)
    RQ(app)

    # Register Jinja template functions
    from .utils import register_template_utils
    register_template_utils(app)

    # Set up asset pipeline
    assets_env = Environment(app)
    dirs = ['assets/styles', 'assets/scripts']
    for path in dirs:
        assets_env.append_path(os.path.join(basedir, path))
    assets_env.url_expire = True

    assets_env.register('app_css', app_css)
    assets_env.register('default_theme_css', default_theme_css)
    assets_env.register('dark_theme_css', dark_theme_css)
    assets_env.register('app_js', app_js)
    assets_env.register('vendor_css', vendor_css)
    assets_env.register('vendor_js', vendor_js)

    # Configure SSL if platform supports it
    if not app.debug and not app.testing and not app.config['SSL_DISABLE']:
        from flask_sslify import SSLify
        SSLify(app)

    # Create app blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from .main.catalogue import main_constellation as main_constellation
    app.register_blueprint(main_constellation)
    from .main.catalogue import main_deepskyobject as main_deepskyobject
    app.register_blueprint(main_deepskyobject)
    from .main.location import main_location as main_location
    app.register_blueprint(main_location)
    from .main.observation import main_observation as main_observation
    app.register_blueprint(main_observation)
    from .main.skyquality import main_skyquality as main_skyquality
    app.register_blueprint(main_skyquality)
    from .main.userdata import main_userdata as main_userdata
    app.register_blueprint(main_userdata)
    from .main.catalogue import main_star as main_star
    app.register_blueprint(main_star)
    from .main.usersettings import main_usersettings as main_usersettings
    app.register_blueprint(main_usersettings)
    from .main.planner import main_planner as main_planner
    app.register_blueprint(main_planner)

    from .account import account as account_blueprint
    app.register_blueprint(account_blueprint, url_prefix='/account')

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from flask_commonmark import Commonmark
    cm = Commonmark(app)

    return app

@babel.localeselector
def get_locale():
    return 'cs'

