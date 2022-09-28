#!/usr/bin/env python
import os
import subprocess

from flask import (
    request,
    current_app,
    send_from_directory
)

from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell
from redis import Redis
from rq import Connection, Queue, Worker

from app import create_app, db
from app.models import Role, User, UserDsoDescription, DeepskyObject
from config import Config

from app.commons.comet_loader import *
from imports.import_catalogues import import_catalogues
from imports.import_constellations import import_constellations
from imports.import_bsc5_all_json import import_bright_stars_bsc5_json_all
from imports.import_vic import import_vic
from imports.import_wds_double_stars import import_wds_doubles
from imports.import_skyquality import do_import_skyquality_locations
from imports.import_dso_lists import (
    import_billionaries_club,
    import_caldwell,
    import_deep_man_600,
    import_herschel400,
    import_superthin_gx,
    import_holmberg,
    import_abell_pn,
    import_hickson,
    import_vic_list,
    import_rosse,
    import_glahn_pns,
    import_glahn_palomar_gc,
    import_glahn_local_group,
    import_corstjens,
)
from imports.import_utils import progress

from imports.import_star_lists import import_carbon_stars
from imports.import_hnsky import import_hnsky, fix_masters_after_hnsky_import
from imports.import_hnsky_fixes import fix_cstar_from_open_ngc
from imports.import_constellations_positions import import_constellations_positions
from imports.link_star_descriptions import link_star_descriptions_by_var_id, link_star_descriptions_by_double_star_id
from imports.import_minor_planets import import_mpcorb_minor_planets
from imports.import_gottlieb import import_gottlieb
from imports.import_double_star_list import import_herschel500
from imports.import_pgc import import_pgc, create_pgc_update_file_from_simbad, update_pgc_imported_dsos_from_updatefile
from app.main.userdata.gitstore import load_public_content_data_from_git2


app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)

migrate = Migrate()
with app.app_context():
    if db.engine.url.drivername == 'sqlite':
        migrate.init_app(app, db, render_as_batch=True)
    else:
        migrate.init_app(app, db)


@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(current_app.static_folder, request.path[1:])


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
                user_name='admin',
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
    import_bright_stars_bsc5_json_all('data/bsc5-all.json')
    import_hnsky('data/deep_sky.hnd')
    fix_masters_after_hnsky_import()
    import_vic('data/vic.csv')
    fix_cstar_from_open_ngc('data/OpenNGC.csv')
    import_pgc('data/PGC.dat')
    import_constellations_positions('data/constlabel.cla')
    import_wds_doubles('data/BruceMacEvoy_doubles.csv.gz')


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
    import_hickson('data/dsolist/Hickson.csv')
    import_billionaries_club('data/dsolist/BillionairesClub.csv')
    import_deep_man_600('data/dsolist/DeepMan600.csv')


@manager.command
def import_star_list():
    import_carbon_stars('data/starlist/CarbonStars.txt')


@manager.command
def import_double_star_list():
    import_herschel500('data/doublestarlist/Herschel500.csv')


@manager.command
def import_minor_planets():
    import_mpcorb_minor_planets('data/MPCORB.9999.DAT')


@manager.command
def import_comets():
    all_mpc_comets = load_all_mpc_comets()
    import_update_comets(all_mpc_comets, show_progress=True)
    update_evaluated_comet_brightness(all_comets=all_mpc_comets, show_progress=True)
    update_comets_cobs_observations()
    update_comets_positions()


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
    if current_app.config.get('EDITOR_USER_NAME_CS'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_CS'), current_app.config.get('EDITOR_USER_NAME_CS'))
    if current_app.config.get('EDITOR_USER_NAME_EN'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_EN'), current_app.config.get('EDITOR_USER_NAME_EN'))
    add_help_user('skyquality', 'skyquality')


def add_help_user(user_name, user_email):
    if User.query.filter_by(email=user_email).first() is None:
        user = User(
            user_name=user_name,
            full_name='',
            password='',
            confirmed=True,
            email=user_email,
            is_hidden=True)
        db.session.add(user)
        db.session.commit()


@manager.command
def add_anonymous_user():
    user_email = 'anonymous@test.test'
    if User.query.filter_by(email=user_email).first() is None:
        role = Role.query.filter_by(name='User').first()
        user = User(
            user_name='anonymous',
            full_name='Anonymous user',
            password='nologin',
            confirmed=True,
            email=user_email,
            role=role,
            )
        db.session.add(user)
        db.session.commit()


@manager.command
def update_dso_axis_ratio():
    all_count = DeepskyObject.query.count()
    i = 0
    for dso in DeepskyObject.query.all():
        axis_ratio = 1
        if dso.major_axis is not None and dso.minor_axis is not None:
            major, minor = dso.major_axis, dso.minor_axis
            if major < minor:
                major, minor = minor, major
            if major > 0:
                axis_ratio = minor / major
        dso.axis_ratio = axis_ratio
        db.session.add(dso)
        progress(i, all_count, 'Updating DSOs axis ratio...')
        i += 1
    db.session.commit()
    print('')


@manager.command
def sync_en_descr_rating():
    editor_cs = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_CS')).first()
    editor_en = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_EN')).first()
    descrs_cs = UserDsoDescription.query.filter_by(user_id=editor_cs.id, lang_code='cs').all()
    for descr in descrs_cs:
        descr_en = UserDsoDescription.query.filter_by(user_id=editor_en.id, lang_code='en', dso_id=descr.dso_id).first()
        if descr_en:
            descr_en.rating = descr.rating
            db.session.add(descr_en)
    db.session.commit()


@manager.command
def import_git_content():
    git_content_repository = os.environ.get('GIT_CONTENT_REPOSITORY')
    if git_content_repository:
        load_public_content_data_from_git2(user_name=current_app.config.get('EDITOR_USER_NAME_CS'), git_content_repository=git_content_repository)
    else:
        print('GIT_CONTENT_REPOSITORY is not configured.')


@manager.command
def import_gottlieb():
    import_gottlieb('data/gottlieb')


@manager.command
def tmp_update_hnsky():
    import_hnsky('data/deep_sky.hnd')


@manager.command
def tmp_import_corstjens():
    import_corstjens('data/dsolist/Corstjens.csv')


@manager.command
def tmp_import_hickson():
    import_hickson('data/dsolist/Hickson.csv')


@manager.command
def tmp_local_group():
    import_glahn_local_group('data/dsolist/LocalGroup.csv')


@manager.command
def tmp_import_pgc():
    import_pgc('data/PGC.dat')


@manager.command
def tmp_constellations():
    import_constellations('data/88-constellations.csv')


@manager.command
def tmp_update_comets_cobs():
    CometObservation.query.delete()
    update_comets_cobs_observations()


@manager.command
def tmp_update_comets_positions():
    update_comets_positions()


@manager.command
def tmp_import_billionaries_club():
    import_billionaries_club('data/dsolist/BillionairesClub.csv')


@manager.command
def tmp_fix_masters():
    fix_masters_after_hnsky_import()


@manager.command
def tmp_import_deep_man_600():
    import_deep_man_600('data/dsolist/DeepMan600.csv')


@manager.command
def create_pgc_update_file():
    create_pgc_update_file_from_simbad('data/PGC.dat', 'data/PGC_update.dat')


@manager.command
def update_pgc_imported_dsos():
    update_pgc_imported_dsos_from_updatefile('data/PGC_update.dat')


if __name__ == '__main__':
    manager.run()
