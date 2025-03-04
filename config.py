import os
import sys

from raygun4py.middleware import flask as flask_raygun
import logging
import logging.handlers

PYTHON_VERSION = sys.version_info[0]
if PYTHON_VERSION == 3:
    import urllib.parse
else:
    import urlparse

basedir = os.path.abspath(os.path.dirname(__file__))

if os.path.exists('config.env'):
    print('Importing environment from .env file')
    for line in open('config.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1].replace("\"", "")


class Config:
    APP_NAME = os.environ.get('APP_NAME', 'CzSkY')
    APP_DESCRIPTION = os.environ.get('APP_DESCRIPTION', 'Experience the cosmos with this planetarium-like platform. Explore interactive sky maps, detailed constellation and deep-sky object descriptions, plan your observations, and record them in an observation log—perfect for all levels of visual astronomy enthusiasts.')
    APP_KEYWORDS = os.environ.get('APP_KEYWORDS', 'stronomy, planetarium software, sky maps, constellations, deep-sky objects, DSO, stargazing, star charts, celestial navigation, observation planner, observation log, night sky, visual astronomy, cosmic exploration, astronomy resources')

    if os.environ.get('SECRET_KEY'):
        SECRET_KEY = os.environ.get('SECRET_KEY')
    else:
        SECRET_KEY = 'SECRET_KEY_ENV_VAR_NOT_SET'
        print('SECRET KEY ENV VAR NOT SET! SHOULD NOT SEE IN PRODUCTION')
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True

    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.sendgrid.net')
    MAIL_PORT = os.environ.get('MAIL_PORT', 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', True)
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # Analytics
    GOOGLE_ANALYTICS_ID = os.environ.get('GOOGLE_ANALYTICS_ID', '')
    SEGMENT_API_KEY = os.environ.get('SEGMENT_API_KEY', '')

    # Admin account
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')
    ADMIN_EMAIL = os.environ.get(
        'ADMIN_EMAIL', 'admin@czsky.cz')
    EMAIL_SUBJECT_PREFIX = '[{}]'.format(APP_NAME)
    EMAIL_SENDER = '{app_name} Admin <{email}>'.format(
        app_name=APP_NAME, email=MAIL_USERNAME)

    REDIS_URL = os.getenv('REDISTOGO_URL', 'http://localhost:6379')

    RAYGUN_APIKEY = os.environ.get('RAYGUN_APIKEY')

    # Parse the REDIS_URL to set RQ config variables
    if PYTHON_VERSION == 3:
        urllib.parse.uses_netloc.append('redis')
        url = urllib.parse.urlparse(REDIS_URL)
    else:
        urlparse.uses_netloc.append('redis')
        url = urlparse.urlparse(REDIS_URL)

    RQ_DEFAULT_HOST = url.hostname
    RQ_DEFAULT_PORT = url.port
    RQ_DEFAULT_PASSWORD = url.password
    RQ_DEFAULT_DB = 0

    USER_DATA_DIR = os.environ.get('USER_DATA_DIR')

    EDITOR_USER_NAME_CS = os.environ.get('EDITOR_USER_NAME_CS')
    EDITOR_USER_NAME_EN = os.environ.get('EDITOR_USER_NAME_EN')
    EDITOR_USER_NAME_WIKIPEDIA = os.environ.get('EDITOR_USER_NAME_WIKIPEDIA')

    ALL_EDITORS_USER_NAMES_CS = os.environ.get('ALL_EDITORS_USER_NAMES_CS')
    ALL_EDITORS_USER_NAMES_EN = os.environ.get('ALL_EDITORS_USER_NAMES_EN')

    ANONYMOUS_USER_NAME = os.environ.get('ANONYMOUS_USER_NAME')

    DEFAULT_IMG_DIR = os.environ.get('DEFAULT_IMG_DIR')

    LANGUAGES = ['en', 'cs']

    CHART_FONT = os.environ.get('CHART_FONT')
    PDF_FONT = os.environ.get('PDF_FONT')

    CHART_IMG_FORMATS = os.environ.get('CHART_IMG_FORMATS', 'avif.jpg')

    CHART_JPEG_LOW_QUALITY = os.environ.get('CHART_JPEG_LOW_QUALITY', 80)
    CHART_JPEG_HIGH_QUALITY = os.environ.get('CHART_JPEG_HIGH_QUALITY', 95)

    CHART_AVIF_SPEED = os.environ.get('CHART_AVIF_SPEED', 8)
    CHART_AVIF_LOW_QUALITY = os.environ.get('CHART_AVIF_LOW_QUALITY', 55)
    CHART_AVIF_HIGH_QUALITY = os.environ.get('CHART_AVIF_HIGH_QUALITY', 80)
    CHART_AVIF_THRESHOLD_WIDTH = os.environ.get('CHART_AVIF_THRESHOLD_WIDTH', 768)
    STAR_CATALOG = os.environ.get('STAR_CATALOG', 'nomad')

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    ASSETS_DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite'))
    SQLALCHEMY_BINDS = {
        'sqm_sql': 'sqlite:///' + os.path.join(basedir, 'data-sqm-dev.sqlite')
    }
    @classmethod
    def init_app(cls, app):
        print('THIS APP IS IN DEBUG MODE. \
                YOU SHOULD NOT SEE THIS IN PRODUCTION.')
        handler = logging.handlers.RotatingFileHandler(
            'app.log',
            maxBytes=1024 * 1024)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'data-test.sqlite'))
    SQLALCHEMY_BINDS = {
        'sqm_sql': 'sqlite:///' + os.path.join(basedir, 'data-sqm-test.sqlite')
    }
    WTF_CSRF_ENABLED = False

    @classmethod
    def init_app(cls, app):
        print('THIS APP IS IN TESTING MODE.  \
                YOU SHOULD NOT SEE THIS IN PRODUCTION.')


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'data.sqlite'))
    SQLALCHEMY_BINDS = {
        'sqm_sql': 'sqlite:///' + os.path.join(basedir, 'data-sqm.sqlite')
    }
    SSL_DISABLE = (os.environ.get('SSL_DISABLE', 'True') == 'True')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        assert os.environ.get('SECRET_KEY'), 'SECRET_KEY IS NOT SET!'

        flask_raygun.Provider(app, app.config['RAYGUN_APIKEY']).attach()
        handler = logging.handlers.RotatingFileHandler(
            'app.log',
            maxBytes=1024 * 1024)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)


class HerokuConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # Handle proxy server headers
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)


class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

        # Log to syslog
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
    'heroku': HerokuConfig,
    'unix': UnixConfig
}
