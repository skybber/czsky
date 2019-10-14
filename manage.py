#!/usr/bin/env python
import os
import subprocess

from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell
from redis import Redis
from rq import Connection, Queue, Worker

from app import create_app, db
from app.models import Role, User
from config import Config

from imports.import_catalogues import import_catalogues
from imports.import_constellations import import_constellations
from imports.import_open_ngc import import_open_ngc
from imports.import_abell import import_abell
from imports.import_sh2 import import_sh2
from imports.import_vic import import_vic
from imports.import_8mag import do_import_8mag
from imports.import_skyquality import do_import_skyquality_locations

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)

def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role)

manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

@manager.command
def test():
    """Run the unit tests."""
    import unittest

    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)


@manager.command
def recreate_db():
    """
    Recreates a local database. You probably should not use this on
    production.
    """
    db.drop_all()
    db.create_all()
    db.session.commit()

@manager.option(
    '-n',
    '--number-users',
    default=10,
    type=int,
    help='Number of each model type to create',
    dest='number_users')
def add_fake_data(number_users):
    """
    Adds fake data to the database.
    """
    User.generate_fake(count=number_users)


@manager.command
def add_test_user():
    user_email = 'test@test.test'
    if User.query.filter_by(email=user_email).first() is None:
        user = User(
            user_name='test',
            first_name='test',
            last_name='test',
            password='heslo',
            confirmed=True,
            email=user_email)
        db.session.add(user)
        db.session.commit()

@manager.command
def setup_dev():
    """Runs the set-up needed for local development."""
    setup_general()


@manager.command
def setup_prod():
    """Runs the set-up needed for production."""
    setup_general()


def setup_general():
    """Runs the set-up needed for both local development and production.
       Also sets up first admin user."""
    Role.insert_roles()
    admin_query = Role.query.filter_by(name='Administrator')
    if admin_query.first() is not None:
        if User.query.filter_by(email=Config.ADMIN_EMAIL).first() is None:
            user = User(
                user_name = 'admin',
                first_name='Admin',
                last_name='Account',
                password=Config.ADMIN_PASSWORD,
                confirmed=True,
                email=Config.ADMIN_EMAIL)
            db.session.add(user)
            db.session.commit()
            print('Added administrator {}'.format(user.full_name()))


@manager.command
def run_worker():
    """Initializes a slim rq task queue."""
    listen = ['default']
    conn = Redis(
        host=app.config['RQ_DEFAULT_HOST'],
        port=app.config['RQ_DEFAULT_PORT'],
        db=0,
        password=app.config['RQ_DEFAULT_PASSWORD'])

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()


@manager.command
def format():
    """Runs the yapf and isort formatters over the project."""
    isort = 'isort -rc *.py app/'
    yapf = 'yapf -r -i *.py app/'

    print('Running {}'.format(isort))
    subprocess.call(isort, shell=True)

    print('Running {}'.format(yapf))
    subprocess.call(yapf, shell=True)

@manager.command
def initialize_catalogues():
    """
    Load catalogues
    """
    import_catalogues('data/astro_catalogues.csv')
    import_constellations('data/88-constellations.csv')
    import_open_ngc('data/OpenNGC.csv')
    import_abell('data/Abell.csv')
    import_sh2('data/SH2-2000.csv')
    import_vic('data/vic.csv')

@manager.command
def import_8mag():
    """
    Import 8mag
    """
    do_import_8mag('private_data/8mag', True, 'translations.sqlite', 'data/vic_8mag.csv')

@manager.command
def import_new_skyquality_locations():
    """
    Import new skyquality locations
    """
    do_import_skyquality_locations('data/skyquality.sqlite', False)

@manager.command
def import_all_skyquality_locations():
    """
    Import all skyquality locations
    """
    do_import_skyquality_locations('data/skyquality.sqlite', True)

@manager.command
def add_help_users():
    add_help_user('8mag', '8mag')
    add_help_user('skyquality', 'skyquality')

def add_help_user(user_name, user_email):
    if User.query.filter_by(email=user_email).first() is None:
        user = User(
            user_name = user_name,
            first_name='',
            last_name='',
            password='',
            confirmed=False,
            email=user_email,
            is_hidden=True)
        db.session.add(user)
        db.session.commit()

@manager.command
def add_editor_user():
    user_email = 'editor@test.test'
    if User.query.filter_by(email=user_email).first() is None:
        role = Role.query.filter_by(name='Editor').first()
        user = User(
            user_name='editor',
            first_name='Editor',
            last_name='Editorovic',
            password='heslo',
            confirmed=True,
            email=user_email,
            role=role,
            )
        db.session.add(user)
        db.session.commit()

if __name__ == '__main__':
    manager.run()
