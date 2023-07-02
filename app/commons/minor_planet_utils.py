import numpy as np
import math

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


def update_minor_planets_positions(show_progress=False):
    mpc_minor_planets = get_all_mpc_minor_planets()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()

    sun, earth = eph['sun'], eph['earth']
    constellation_at = load_constellation_map()

    minor_planets = []

    i = 0

    for minor_planet in MinorPlanet.query.all():
        mpc_mplanet = mpc_minor_planets.iloc[minor_planet.int_designation-1]
        if mpc_mplanet is not None:
            skf_mplanet = sun + mpc.mpcorb_orbit(mpc_mplanet, ts, GM_SUN)
            ra_ang, dec_ang, distance = earth.at(t).observe(skf_mplanet).radec()
            minor_planet.cur_ra = ra_ang.radians
            minor_planet.cur_dec = dec_ang.radians
            const_code = constellation_at(position_from_radec(ra_ang.radians / np.pi * 12.0, dec_ang.radians / np.pi * 180.0))
            minor_planet.cur_constell_id = Constellation.get_constellation_by_iau_code(const_code).id if const_code else None

            minor_planets.append(minor_planet)
            if show_progress:
                progress(i, len(mpc_minor_planets), 'Evaluating minor planet positions...')
            elif i % 500 == 0:
                current_app.logger.info('Updated {} minor planets positions.'.format(i))
            i += 1

    _save_minor_planets(minor_planets, show_progress, 'Saving minor planets...')
    current_app.logger.info('Minor planets\' positions updated.')


def _get_apparent_magnitude_hg( H_absolute_magnitude, G_slope, body_earth_distanceAU, body_sun_distanceAU, earth_sun_distanceAU ):
    beta = math.acos(
        (body_sun_distanceAU * body_sun_distanceAU + body_earth_distanceAU * body_earth_distanceAU - earth_sun_distanceAU * earth_sun_distanceAU) /
        (2 * body_sun_distanceAU * body_earth_distanceAU)
    )

    psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 0.63)
    Psi_1 = math.exp(-3.33 * psi_t)
    psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 1.22)
    Psi_2 = math.exp(-1.87 * psi_t)

    # Have found a combination of G_slope, Psi_1 and Psi_2 can lead to a negative value in the log calculation.
    try:
        apparentMagnitude = H_absolute_magnitude + \
                            5.0 * math.log10(body_sun_distanceAU * body_earth_distanceAU) - \
                            2.5 * math.log10((1 - G_slope) * Psi_1 + G_slope * Psi_2)
    except:
        apparentMagnitude = None

    return apparentMagnitude


def update_minor_planets_brightness(show_progress=False):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()

    sun, earth = eph['sun'], eph['earth']

    ra, dec, earth_sun_distance = earth.at(t).observe(sun).apparent().radec()

    mpc_minor_planets = get_all_mpc_minor_planets()

    minor_planets = []
    i = 0

    for minor_planet in MinorPlanet.query.all():
        mpc_minor_planet = mpc_minor_planets.iloc[minor_planet.int_designation - 1]
        body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)
        ra, dec, sun_body_distance = sun.at(t).observe(body).radec()
        ra, dec, earth_body_distance = earth.at(t).observe(body).apparent().radec()

        apparent_magnitude = _get_apparent_magnitude_hg(minor_planet.magnitude_H, minor_planet.magnitude_G,
                                                        earth_body_distance.au, sun_body_distance.au,
                                                        earth_sun_distance.au)
        if apparent_magnitude:
            minor_planet.eval_mag = apparent_magnitude
            minor_planets.append(minor_planet)
        if show_progress:
            progress(i, len(mpc_minor_planets), 'Evaluating minor planet brightness...')
        elif i % 500 == 0:
            current_app.logger.info('Updated {} minor planets brightness.'.format(i))
        i += 1

    _save_minor_planets(minor_planets, show_progress, 'Saving minor planets...')
    current_app.logger.info('Minor planets\' brightnesses updated.')
