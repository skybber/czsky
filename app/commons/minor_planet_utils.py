import numpy as np
import math
import gzip
import io
import os
import re
import requests
import uuid
from functools import lru_cache
from datetime import datetime, timedelta

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
from imports.import_minor_planets import assign_minor_planet_from_mpc_row

utc = dt_module.timezone.utc

all_minor_planets = None
MPCORB_EXCERPT_FILE = 'data/MPCORB.9999.DAT'
MPCORB_FULL_GZ_FILE = 'data/MPCORB.DAT.gz'
MPCORB_URL = 'https://minorplanetcenter.net/iau/MPCORB/MPCORB.DAT.gz'
MPCORB_MAX_AGE = timedelta(days=1)


def get_all_mpc_minor_planets():
    global all_minor_planets
    if all_minor_planets is None:
        with load.open(MPCORB_EXCERPT_FILE) as f:
            all_minor_planets = mpc.load_mpcorb_dataframe(f)
            bad_orbits = all_minor_planets.semimajor_axis_au.isnull()
            all_minor_planets = all_minor_planets[~bad_orbits]
            all_minor_planets['designation_packed'] = all_minor_planets['designation_packed'].astype(str).str.strip()
            all_minor_planets['minor_planet_id'] = all_minor_planets['designation_packed']
            all_minor_planets = all_minor_planets.set_index('designation_packed', drop=False)
    return all_minor_planets


def reset_minor_planets_cache():
    global all_minor_planets
    all_minor_planets = None
    _get_minor_planet_cached.cache_clear()


def _get_minor_planet_mpc_designation(minor_planet):
    if hasattr(minor_planet, 'mpc_designation'):
        if minor_planet.mpc_designation:
            return str(minor_planet.mpc_designation).strip()
        if minor_planet.int_designation:
            return '{:05d}'.format(int(minor_planet.int_designation))
    if isinstance(minor_planet, int):
        return '{:05d}'.format(minor_planet)
    if isinstance(minor_planet, str):
        return minor_planet.strip()
    return '{:05d}'.format(int(minor_planet))


def find_mpc_minor_planet(minor_planet):
    mpc_designation = _get_minor_planet_mpc_designation(minor_planet)
    return get_all_mpc_minor_planets().loc[mpc_designation]


def get_mpc_minor_planet_position(mpc_minor_planet, dt):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))
    skf_mplanet = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    ra_ang, dec_ang, _ = earth.at(t).observe(skf_mplanet).radec()
    return ra_ang, dec_ang


def _normalize_to_300s(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    else:
        dt = dt.astimezone(utc)

    timestamp = dt.timestamp()
    floored = math.floor(timestamp / 300) * 300
    return datetime.fromtimestamp(floored, tz=utc)


@lru_cache(maxsize=256)
def _get_minor_planet_cached(minor_planet_mpc_designation: str, dt: datetime):
    mpc_minor_planet = find_mpc_minor_planet(minor_planet_mpc_designation)
    ra_ang, dec_ang = get_mpc_minor_planet_position(mpc_minor_planet, dt)
    return ra_ang.radians, dec_ang.radians


def get_minor_planet_radec(minor_planet, dt: datetime):
    normalized_dt = _normalize_to_300s(dt)
    return _get_minor_planet_cached(_get_minor_planet_mpc_designation(minor_planet), normalized_dt)


def _calculate_minor_planet_current_values(minor_planet, mpc_minor_planet, ts, eph, t, constellation_at):
    sun, earth = eph['sun'], eph['earth']
    skf_mplanet = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)
    ra_ang, dec_ang, _ = earth.at(t).observe(skf_mplanet).radec()
    minor_planet.cur_ra = ra_ang.radians
    minor_planet.cur_dec = dec_ang.radians
    const_code = constellation_at(position_from_radec(ra_ang.radians / np.pi * 12.0, dec_ang.radians / np.pi * 180.0))
    minor_planet.cur_constell_id = Constellation.get_constellation_by_iau_code(const_code).id if const_code else None

    sun_ra_ang, sun_dec_ang, _ = earth.at(t).observe(sun).radec()
    minor_planet.cur_angular_dist_from_sun = np.arccos(
        np.sin(dec_ang.radians) * np.sin(sun_dec_ang.radians) +
        np.cos(dec_ang.radians) * np.cos(sun_dec_ang.radians) *
        np.cos(ra_ang.radians - sun_ra_ang.radians)
    )


def update_minor_planet_position(minor_planet, mpc_minor_planet=None):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()
    constellation_at = load_constellation_map()
    if mpc_minor_planet is None:
        mpc_minor_planet = find_mpc_minor_planet(minor_planet)
    _calculate_minor_planet_current_values(minor_planet, mpc_minor_planet, ts, eph, t, constellation_at)


def update_minor_planet_brightness(minor_planet, mpc_minor_planet=None):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()
    sun, earth = eph['sun'], eph['earth']
    if mpc_minor_planet is None:
        mpc_minor_planet = find_mpc_minor_planet(minor_planet)
    _, _, earth_sun_distance = earth.at(t).observe(sun).apparent().radec()
    body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)
    _, _, sun_body_distance = sun.at(t).observe(body).radec()
    _, _, earth_body_distance = earth.at(t).observe(body).apparent().radec()
    apparent_magnitude = _get_apparent_magnitude_hg(minor_planet.magnitude_H, minor_planet.magnitude_G,
                                                    earth_body_distance.au, sun_body_distance.au,
                                                    earth_sun_distance.au)
    if apparent_magnitude:
        minor_planet.eval_mag = apparent_magnitude


def _save_minor_planets(minor_planets, show_progress, progress_title):
    try:
        line_cnt = 1
        commit_cnt = 0
        for minor_planet in minor_planets:
            if show_progress:
                progress(line_cnt, len(minor_planets), progress_title)
            line_cnt += 1
            db.session.add(minor_planet)
            commit_cnt += 1
            if commit_cnt % 100 == 0:
                db.session.commit()
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

    constellation_at = load_constellation_map()

    minor_planets = []

    i = 0

    for minor_planet in MinorPlanet.query.all():
        mpc_mplanet = find_mpc_minor_planet(minor_planet)
        if mpc_mplanet is not None:
            _calculate_minor_planet_current_values(minor_planet, mpc_mplanet, ts, eph, t, constellation_at)
            minor_planets.append(minor_planet)
            if show_progress:
                progress(i, len(mpc_minor_planets), 'Evaluating minor planet positions...')
            elif i % 500 == 0:
                current_app.logger.info('Updated {} minor planets positions.'.format(i))
            i += 1

    _save_minor_planets(minor_planets, show_progress, 'Saving minor planets...')
    current_app.logger.info('Minor planets\' positions updated.')


def _get_apparent_magnitude_hg( H_absolute_magnitude, G_slope, body_earth_distanceAU, body_sun_distanceAU, earth_sun_distanceAU ):
    fac = (body_sun_distanceAU**2 + body_earth_distanceAU**2 - earth_sun_distanceAU**2) / (2 * body_sun_distanceAU * body_earth_distanceAU)
    if fac < -1:
        fac = -1
    if fac > 1:
        fac = 1
    beta = math.acos(fac)

    # Have found a combination of G_slope, Psi_1 and Psi_2 can lead to a negative value in the log calculation.
    try:
        psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 0.63)
        Psi_1 = math.exp(-3.33 * psi_t)
        psi_t = math.exp(math.log(math.tan(beta / 2.0)) * 1.22)
        Psi_2 = math.exp(-1.87 * psi_t)

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
        mpc_minor_planet = find_mpc_minor_planet(minor_planet)
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


def _mpcorb_file_is_fresh(file_path):
    if not os.path.exists(file_path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=utc)
    return datetime.now(tz=utc) - mtime <= MPCORB_MAX_AGE


def ensure_full_mpcorb_file(force_reload=False):
    if not force_reload and _mpcorb_file_is_fresh(MPCORB_FULL_GZ_FILE):
        return MPCORB_FULL_GZ_FILE

    data_dir = os.path.dirname(MPCORB_FULL_GZ_FILE)
    os.makedirs(data_dir, exist_ok=True)
    tmp_file_path = os.path.join(data_dir, 'MPCORB.DAT.{}.gz.tmp'.format(uuid.uuid4().hex))
    response = requests.get(MPCORB_URL, stream=True)
    if response.status_code != 200:
        raise RuntimeError('Download MPCORB.DAT.gz failed. url={}'.format(MPCORB_URL))
    with open(tmp_file_path, 'wb') as f:
        f.write(response.raw.read())
    os.rename(tmp_file_path, MPCORB_FULL_GZ_FILE)
    return MPCORB_FULL_GZ_FILE


def _normalize_minor_planet_query(query):
    return ' '.join((query or '').replace('"', '').strip().split()).lower()


def _mpcorb_line_matches(line, query):
    normalized_query = _normalize_minor_planet_query(query)
    if not normalized_query:
        return False

    packed_designation = line[:7].strip().lower()
    normalized_line = ' '.join(line.strip().lower().split())
    if normalized_query == packed_designation:
        return True
    if normalized_query.isdigit() and '({})'.format(int(normalized_query)) in normalized_line:
        return True
    if normalized_query.isdigit():
        return False
    return normalized_query in normalized_line


def find_mpcorb_line_by_designation(query, mpcorb_file=None):
    mpcorb_file = mpcorb_file or ensure_full_mpcorb_file()
    opener = gzip.open if mpcorb_file.endswith('.gz') else open
    with opener(mpcorb_file, 'rt', encoding='ascii', errors='ignore') as f:
        for current_row, line in enumerate(f, start=1):
            if current_row < 44 and not line[:7].strip():
                continue
            if _mpcorb_line_matches(line, query):
                return line
    return None


def _load_mpcorb_line(line):
    minor_planets = mpc.load_mpcorb_dataframe(io.BytesIO(line.encode('ascii')))
    bad_orbits = minor_planets.semimajor_axis_au.isnull()
    minor_planets = minor_planets[~bad_orbits]
    if minor_planets.empty:
        return None
    return minor_planets.iloc[0]


def _append_mpcorb_excerpt_line(line):
    mpc_designation = line[:7].strip()
    if os.path.exists(MPCORB_EXCERPT_FILE):
        with open(MPCORB_EXCERPT_FILE, 'r', encoding='ascii', errors='ignore') as f:
            for existing_line in f:
                if existing_line[:7].strip() == mpc_designation:
                    return
    with open(MPCORB_EXCERPT_FILE, 'a', encoding='ascii') as f:
        if not line.endswith('\n'):
            line += '\n'
        f.write(line)


def append_mpcorb_excerpt_lines_by_designations(mpc_designations, mpcorb_file=None):
    needed_designations = {str(x).strip() for x in mpc_designations if x}
    if not needed_designations:
        return

    existing_designations = set()
    if os.path.exists(MPCORB_EXCERPT_FILE):
        with open(MPCORB_EXCERPT_FILE, 'r', encoding='ascii', errors='ignore') as f:
            existing_designations = {line[:7].strip() for line in f}
    needed_designations -= existing_designations
    if not needed_designations:
        return

    mpcorb_file = mpcorb_file or ensure_full_mpcorb_file()
    opener = gzip.open if mpcorb_file.endswith('.gz') else open
    found_lines = []
    with opener(mpcorb_file, 'rt', encoding='ascii', errors='ignore') as f:
        for line in f:
            if line[:7].strip() in needed_designations:
                found_lines.append(line)
                needed_designations.remove(line[:7].strip())
                if not needed_designations:
                    break

    if found_lines:
        with open(MPCORB_EXCERPT_FILE, 'a', encoding='ascii') as f:
            for line in found_lines:
                if not line.endswith('\n'):
                    line += '\n'
                f.write(line)


def import_minor_planet_by_designation(query):
    line = find_mpcorb_line_by_designation(query)
    if line is None:
        return None

    mpc_minor_planet = _load_mpcorb_line(line)
    if mpc_minor_planet is None:
        return None

    mpc_designation = str(mpc_minor_planet['designation_packed']).strip()
    minor_planet = MinorPlanet.query.filter_by(mpc_designation=mpc_designation).first()
    if minor_planet is None:
        int_designation = None
        designation_match = re.match(r'^\((\d+)\)', str(mpc_minor_planet['designation'] or ''))
        if designation_match:
            int_designation = int(designation_match.group(1))
        else:
            try:
                int_designation = int(mpc_designation)
            except ValueError:
                pass
        if int_designation is not None:
            minor_planet = MinorPlanet.query.filter_by(int_designation=int_designation).first()
    if minor_planet is None:
        minor_planet = MinorPlanet()

    assign_minor_planet_from_mpc_row(minor_planet, mpc_minor_planet)
    _append_mpcorb_excerpt_line(line)
    reset_minor_planets_cache()
    update_minor_planet_position(minor_planet, mpc_minor_planet)
    update_minor_planet_brightness(minor_planet, mpc_minor_planet)
    db.session.add(minor_planet)
    db.session.commit()
    return minor_planet
