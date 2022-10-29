import numpy as np

from sqlalchemy.exc import IntegrityError

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.api import position_from_radec, load_constellation_map

import datetime as dt_module

from flask import (
    current_app,
)

from app.models import Constellation, MinorPlanet

from app import db

from imports.import_utils import progress

utc = dt_module.timezone.utc

all_minor_planets = None


def get_all_mpc_minor_planets():
    global all_minor_planets
    if all_minor_planets is None:
        with load.open('data/MPCORB.9999.DAT') as f:
            all_minor_planets = mpc.load_mpcorb_dataframe(f)
            bad_orbits = all_minor_planets.semimajor_axis_au.isnull()
            all_minor_planets = all_minor_planets[~bad_orbits]
            all_minor_planets['minor_planet_id'] = all_minor_planets['designation_packed']
    return all_minor_planets


def find_mpc_minor_planet(mplanet_int_designation):
    return get_all_mpc_minor_planets().iloc[mplanet_int_designation - 1]


def get_mpc_minor_planet_position(mpc_minor_planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))
    skf_mplanet = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    ra_ang, dec_ang, distance = earth.at(t).observe(skf_mplanet).radec()
    return ra_ang, dec_ang


def _save_minor_planets(minor_planets, show_progress, progress_title):
    try:
        line_cnt = 1
        for minor_planet in minor_planets:
            if show_progress:
                progress(line_cnt, len(minor_planets), progress_title)
            line_cnt += 1
            db.session.add(minor_planet)
        if show_progress:
            print('')
        db.session.commit()
    except IntegrityError as err:
        current_app.logger.error('\nIntegrity error {}'.format(err))
        db.session.rollback()


def update_minor_planets_positions(all_mpc_minor_planets=None, show_progress=False):
    if all_mpc_minor_planets is None:
        all_mpc_minor_planets = get_all_mpc_minor_planets()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()

    sun, earth = eph['sun'], eph['earth']
    constellation_at = load_constellation_map()

    minor_planets = []

    i = 0

    for db_mplanet in MinorPlanet.query.all():
        mpc_mplanet = all_mpc_minor_planets.iloc[db_mplanet.int_designation-1]
        if mpc_mplanet is not None:
            skf_mplanet = sun + mpc.mpcorb_orbit(mpc_mplanet, ts, GM_SUN)
            ra_ang, dec_ang, distance = earth.at(t).observe(skf_mplanet).radec()
            db_mplanet.cur_ra = ra_ang.radians
            db_mplanet.cur_dec = dec_ang.radians
            const_code = constellation_at(position_from_radec(ra_ang.radians / np.pi * 12.0, dec_ang.radians / np.pi * 180.0))
            db_mplanet.cur_constell_id = Constellation.get_constellation_by_iau_code(const_code).id if const_code else None

            minor_planets.append(db_mplanet)
            if show_progress:
                progress(i, len(all_mpc_minor_planets), 'Evaluating minor planet positions...')
                i += 1

    _save_minor_planets(minor_planets, show_progress, 'Saving minor planets...')
    current_app.logger.info('Minor planets\' positions updated.')
