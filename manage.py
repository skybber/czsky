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
from imports.import_bsc5 import import_bright_stars_bsc5
from imports.import_vic import import_vic
from imports.import_skyquality import do_import_skyquality_locations
from imports.normalize_glahn_img import normalize_glahn_img
from imports.import_dso_lists import import_caldwell, import_herschel400, import_superthin_gx, import_holmberg, import_abell_pn
from imports.import_dso_lists import import_vic_list, import_rosse, import_glahn_pns, import_glahn_palomar_gc, import_glahn_local_group
from imports.import_gottlieb import import_gottlieb
from imports.import_hnsky import import_hnsky
from imports.import_hnsky_fixes import fix_cstar_from_open_ngc
from imports.import_constellations_positions import import_constellations_positions

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)

migrate = Migrate()
with app.app_context():
    if db.engine.url.drivername == 'sqlite':
        migrate.init_app(app, db, render_as_batch=True)
    else:
        migrate.init_app(app, db)


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
                full_name='Admin Account',
                password=Config.ADMIN_PASSWORD,
                confirmed=True,
                email=Config.ADMIN_EMAIL)
            db.session.add(user)
            db.session.commit()
            print('Added administrator {}'.format(user.full_name))


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
    import_bright_stars_bsc5('data/bsc5.dat')
    import_hnsky('data/deep_sky.hnd')
    import_vic('data/vic.csv')
    fix_cstar_from_open_ngc('data/OpenNGC.csv')
    import_constellations_positions('data/constlabel.cla')

@manager.command
def import_dso_list():
    import_caldwell('data/dsolist/CaldwellObjects.csv')
    import_herschel400('data/dsolist/Herschel400.csv')
    import_superthin_gx('data/dsolist/SuperthinGX.csv')
    import_holmberg('data/dsolist/Holmberg.csv')
    import_abell_pn('data/dsolist/AbellPN.csv')
    import_vic_list('data/dsolist/Vic.csv')
    import_rosse('data/dsolist/RosseSpirals.csv')
    import_glahn_pns('data/dsolist/Glahn_PN.csv')
    import_glahn_palomar_gc('data/dsolist/PalomarGC.csv')
    import_glahn_local_group('data/dsolist/LocalGroup.csv')

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
def add_test_user():
    user_email = 'test@test.test'
    if User.query.filter_by(email=user_email).first() is None:
        user = User(
            user_name='test',
            full_name='test',
            password='nologin',
            confirmed=True,
            email=user_email)
        db.session.add(user)
        db.session.commit()

@manager.command
def add_help_users():
    add_help_user('8mag', '8mag')
    add_help_user('s.gottlieb', 's.gottlieb')
    add_help_user('skyquality', 'skyquality')

def add_help_user(user_name, user_email):
    if User.query.filter_by(email=user_email).first() is None:
        user = User(
            user_name = user_name,
            full_name='',
            password='',
            confirmed=True,
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
            full_name='Editor Editorovic',
            password='nologin',
            confirmed=True,
            email=user_email,
            role=role,
            )
        db.session.add(user)
        db.session.commit()

# TODO: remove
@manager.command
def tmp_normalize_glahn_img():
    """
    Link star descriptions
    """
    normalize_glahn_img('app/static/webassets-external/users/glahn.src', 'app/static/webassets-external/users/glahn/img/dso/')

@manager.command
def tmp_import_gottlieb():
    add_help_user('s.gottlieb', 's.gottlieb')
    import_gottlieb('data/gottlieb')

@manager.command
def tmp_import_glahn_local_group():
    import_glahn_local_group('data/dsolist/LocalGroup.csv')

@manager.command
def tmp_import_abell_pn():
    import_abell_pn('data/dsolist/AbellPN.csv')

@manager.command
def tmp_import_constellations_positions():
    import_constellations_positions('data/constlabel.cla')


if __name__ == '__main__':
    manager.run()
