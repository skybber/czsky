#!/usr/bin/env python

import os
import subprocess
from datetime import datetime

from flask import (
    current_app,
    request,
    send_from_directory
)

from config import Config
from sqlalchemy import func

from flask_migrate import Migrate #, MigrateCommand

from app import create_app, db

from app.models import (
    Constellation,
    ChartTheme,
    Role,
    User,
    UserDsoDescription,
    DeepskyObject,
    UserDsoApertureDescription,
)

from imports.import_utils import progress

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

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

@app.cli.command("test")
def test():
    """Run the unit tests."""
    import unittest

    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)


@app.cli.command("recreate_db")
def recreate_db():
    """
    Recreates a local database. You probably should not use this on
    production.
    """
    db.drop_all()
    db.create_all()
    db.session.commit()


@app.cli.command("setup_dev")
def setup_dev():
    """Runs the set-up needed for local development."""
    setup_general()


@app.cli.command("setup_prod")
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


@app.cli.command("run_worker")
def run_worker():
    """Initializes a slim rq task queue."""
    listen = ['default']
    from redis import Redis
    from rq import Connection, Queue, Worker
    conn = Redis(
        host=app.config['RQ_DEFAULT_HOST'],
        port=app.config['RQ_DEFAULT_PORT'],
        db=0,
        password=app.config['RQ_DEFAULT_PASSWORD'])

    with Connection(conn):
        worker = Worker(map(Queue, listen), connection=conn)
        worker.work()


@app.cli.command("format")
def format():
    """Runs the yapf and isort formatters over the project."""
    isort = 'isort -rc *.py app/'
    yapf = 'yapf -r -i *.py app/'

    print('Running {}'.format(isort))
    subprocess.call(isort, shell=True)

    print('Running {}'.format(yapf))
    subprocess.call(yapf, shell=True)


@app.cli.command("initialize_catalogues")
def initialize_catalogues():
    """
    Load catalogues
    """
    from imports.import_catalogues import import_catalogues
    from imports.import_constellations import import_constellations
    from imports.import_bsc5_all_json import import_bright_stars_bsc5_json_all
    from imports.import_hnsky import import_hnsky, fix_masters_after_hnsky_import
    from imports.import_vic import import_vic
    from imports.import_wds_double_stars import import_wds_doubles
    from imports.import_hnsky_fixes import fix_cstar_from_open_ngc
    from imports.import_constellations_positions import import_constellations_positions
    from imports.import_pgc import import_pgc
    from imports.import_collinder import import_collinder

    import_catalogues('data/astro_catalogues.csv')
    import_constellations('data/88-constellations.csv')
    import_bright_stars_bsc5_json_all('data/bsc5-all.json')
    import_hnsky('data/deep_sky.hnd')
    fix_masters_after_hnsky_import()
    import_vic('data/vic.csv')
    fix_cstar_from_open_ngc('data/OpenNGC.csv')
    import_pgc('data/PGC.dat')
    import_collinder('data/collinder.txt')
    import_constellations_positions('data/constlabel.cla')
    import_wds_doubles('data/BruceMacEvoy_doubles.csv.gz')


@app.cli.command("import_dso_list")
def import_dso_list():
    from imports.import_dso_lists import import_billionaries_club
    from imports.import_dso_lists import import_caldwell
    from imports.import_dso_lists import import_deep_man_600
    from imports.import_dso_lists import import_herschel400
    from imports.import_dso_lists import import_superthin_gx
    from imports.import_dso_lists import import_holmberg
    from imports.import_dso_lists import import_abell_pn
    from imports.import_dso_lists import import_hickson
    from imports.import_dso_lists import import_vic_list
    from imports.import_dso_lists import import_rosse
    from imports.import_dso_lists import import_glahn_pns
    from imports.import_dso_lists import import_glahn_palomar_gc
    from imports.import_dso_lists import import_glahn_local_group

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


@app.cli.command("import_hnsky_supplements")
def import_hnsky_supplements():
    from imports.import_hnsky_supplement import import_hnsky_supplement
    import_hnsky_supplement('data/supplements/M31 global clusters, Revised Bologna Catalogue v5.sup', allowed_cat_prefixes = ['Bol', 'SKHB'])
    import_hnsky_supplement('data/supplements/M33 global clusters,  2007 catalog.sup', allowed_cat_prefixes = ['CBF'])
    import_hnsky_supplement('data/supplements/VDB, catalogue of reflection nebulae.sup')


@app.cli.command("import_star_list")
def import_star_list():
    from imports.import_star_lists import import_carbon_stars
    import_carbon_stars('data/starlist/CarbonStars.txt')


@app.cli.command("import_double_star_list")
def import_double_star_list():
    from imports.import_double_star_list import import_herschel500
    from imports.import_double_star_list import import_dmichalko
    import_herschel500('data/doublestarlist/Herschel500.csv')
    import_dmichalko('data/doublestarlist/DMichalko.csv')


@app.cli.command("import_minor_planets")
def import_minor_planets():
    from imports.import_minor_planets import import_mpcorb_minor_planets
    from app.commons.minor_planet_utils import update_minor_planets_positions, update_minor_planets_brightness
    import_mpcorb_minor_planets('data/MPCORB.9999.DAT')
    update_minor_planets_positions(True)
    update_minor_planets_brightness(True)


@app.cli.command("import_comets")
def import_comets():
    from app.commons.comet_utils import (load_all_mpc_comets, import_update_comets, update_evaluated_comet_brightness,
                                         update_comets_cobs_observations, update_comets_positions)
    all_mpc_comets = load_all_mpc_comets(True)
    import_update_comets(all_mpc_comets, show_progress=True)
    update_evaluated_comet_brightness(all_mpc_comets=all_mpc_comets, show_progress=True)
    update_comets_cobs_observations()
    update_comets_positions(None, True)


@app.cli.command("import_planets")
def import_planets():
    from imports.import_planets import import_db_planets
    import_db_planets()


@app.cli.command("import_supernovae")
def import_supernovae():
    from app.commons.supernova_loader import update_supernovae_from_rochesterastronomy
    update_supernovae_from_rochesterastronomy()


@app.cli.command("import_new_skyquality_locations")
def import_new_skyquality_locations():
    """
    Import new skyquality locations
    """
    from imports.import_skyquality import do_import_skyquality_locations
    do_import_skyquality_locations('data/skyquality.sqlite', False)


@app.cli.command("import_all_skyquality_locations")
def import_all_skyquality_locations():
    """
    Import all skyquality locations
    """
    from imports.import_skyquality import do_import_skyquality_locations
    do_import_skyquality_locations('data/skyquality.sqlite', True)


@app.cli.command("add_help_users")
def add_help_users():
    if current_app.config.get('EDITOR_USER_NAME_CS'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_CS'), current_app.config.get('EDITOR_USER_NAME_CS'))
    if current_app.config.get('EDITOR_USER_NAME_EN'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_EN'), current_app.config.get('EDITOR_USER_NAME_EN'))
    if current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'), current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'))
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


@app.cli.command("add_anonymous_user")
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


@app.cli.command("update_dso_axis_ratio")
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


@app.cli.command("sync_en_descr_rating")
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


@app.cli.command("import_git_content")
def import_git_content():
    from app.main.userdata.gitstore import load_public_content_data_from_git2
    git_content_repository = os.environ.get('GIT_CONTENT_REPOSITORY')
    if git_content_repository:
        load_public_content_data_from_git2(user_name=current_app.config.get('EDITOR_USER_NAME_CS'), git_content_repository=git_content_repository)
    else:
        print('GIT_CONTENT_REPOSITORY is not configured.')


@app.cli.command("import_gottlieb")
def import_gottlieb():
    from imports.import_gottlieb import import_gottlieb
    import_gottlieb('data/gottlieb')

@app.cli.command("create_pgc_update_file")
def create_pgc_update_file():
    from imports.import_pgc import create_pgc_update_file_from_simbad
    create_pgc_update_file_from_simbad('data/PGC.dat', 'data/PGC_update.dat')


@app.cli.command("update_pgc_imported_dsos")
def update_pgc_imported_dsos():
    from imports.import_pgc import update_pgc_imported_dsos_from_updatefile
    update_pgc_imported_dsos_from_updatefile('data/PGC_update.dat')


def _create_update_theme(user, name, definition):
    t = ChartTheme.query.filter_by(name=name)
    if not t:
        t = ChartTheme()
        t.is_public = True
        t.name = name
        t.user_id = user.id
        t.is_public = True
        t.create_by = user.id
        t.create_date = datetime.now()
    t.definition = definition
    t.update_by = user.id
    t.update_date = datetime.now()
    db.session.add(t)


@app.cli.command("create_update_basic_chart_themes")
def create_update_basic_chart_themes():
    from app.commons.chart_theme_definition import BASE_THEME_TEMPL, DARK_THEME_TEMPL, NIGHT_THEME_TEMPL, LIGHT_THEME_TEMPL
    user = User.query.filter_by(user_name='admin').first()
    _create_update_theme(user, 'base_theme', BASE_THEME_TEMPL)
    _create_update_theme(user, 'dark_theme', DARK_THEME_TEMPL)
    _create_update_theme(user, 'night_theme', NIGHT_THEME_TEMPL)
    _create_update_theme(user, 'light_theme', LIGHT_THEME_TEMPL)
    db.session.commit()


@app.cli.command("tmp_import_translated_gottlieb")
def tmp_import_translated_gottlieb():
    from imports.import_gottlieb_translate import import_translated_gottlieb
    import_translated_gottlieb('data/gottlieb', 'cs', 'Autor textu: ')

@app.cli.command("tmp_import_translated_stars")
def tmp_import_translated_stars():
    from imports.import_stars_translate import import_stars_translate
    import_stars_translate()


@app.cli.command("tmp_add_user_wikipedia")
def tmp_add_user_wikipedia():
    if current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'):
        add_help_user(current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'), current_app.config.get('EDITOR_USER_NAME_WIKIPEDIA'))


@app.cli.command("tmp_import_wikipedia_ngc")
def tmp_import_wikipedia_ngc():
    from imports.import_wiki_ngc_ic import import_wikipedia_ngc
    import_wikipedia_ngc()


@app.cli.command("tmp_translate_wikipedia_ngc")
def tmp_translate_wikipedia_ngc():
    from imports.import_wiki_ngc_ic import translate_wikipedia_ngc
    gpt_prompt = '''Přelož následující text popisu astronomického objektu češtiny. Překládaná text začína sekvencí __0__. Nikdy neodstraňuj značky typu __0__ :

'''
    translate_wikipedia_ngc('cs', 'Zdroj', gpt_prompt)


@app.cli.command("tmp_dmichalko")
def tmp_dmichalko():
    from imports.import_double_star_list import import_dmichalko
    import_dmichalko('data/doublestarlist/DMichalko.csv')


@app.cli.command("tmp_add_ug_bl_user_dso_desc")
def tmp_add_ug_bl_user_dso_desc():
    from app.commons.auto_img_utils import get_ug_bl_dsos
    editor_cs = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_CS')).first()

    str_all_editors = current_app.config.get('ALL_EDITORS_USER_NAMES_CS')
    if str_all_editors:
        all_editors_ar = [x.strip() for x in str_all_editors.split(',')]
        all_editors = User.query.filter(User.user_name.in_(all_editors_ar)).all()
    else:
        all_editors = ( editor_cs, )

    if editor_cs:
        for constellation in Constellation.get_all():
            constell_ug_bl_dsos = get_ug_bl_dsos()[constellation.id]
            for dso_id in constell_ug_bl_dsos:
                dso = constell_ug_bl_dsos[dso_id]
                udd = UserDsoDescription.query.filter_by(user_id=editor_cs.id, dso_id=dso_id, lang_code='cs').first()
                if not udd:
                    has_descr = False
                    for editor_user in all_editors:
                        user_apert_descrs = UserDsoApertureDescription.query.filter_by(dso_id=dso.id,
                                                                                       user_id=editor_user.id,
                                                                                       lang_code='cs') \
                            .filter(func.coalesce(UserDsoApertureDescription.text, '') != '') \
                            .all()
                        if user_apert_descrs:
                            has_descr = True

                    if has_descr:
                        print('Adding {}'.format(dso.name))
                        udd = UserDsoDescription(
                            dso_id=dso.id,
                            user_id=editor_cs.id,
                            rating=0,
                            lang_code='cs',
                            cons_order=100000,
                            text='',
                            references=None,
                            common_name=dso.common_name,
                            create_by=editor_cs.id,
                            update_by=editor_cs.id,
                            create_date=datetime.now(),
                            update_date=datetime.now(),
                        )
                        db.session.add(udd)
                        db.session.flush()
                        db.session.commit()
@app.cli.command("tmp_update_minor_planets_brightness")
def tmp_update_minor_planets_brightness():
    from app.commons.minor_planet_utils import update_minor_planets_brightness
    update_minor_planets_brightness(True)

@app.cli.command("tmp_update_hnsky")
def tmp_update_hnsky():
    from imports.import_hnsky import import_hnsky, fix_masters_after_hnsky_import
    import_hnsky('data/deep_sky.hnd')
