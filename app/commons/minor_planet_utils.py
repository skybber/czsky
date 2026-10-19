import numpy as np
import pandas as pd
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

from skyfield.api import load, wgs84
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
NEA_FILE = 'data/NEA.txt'
NEA_URL = 'https://minorplanetcenter.net/iau/MPCORB/NEA.txt'
NEA_MAX_AGE = timedelta(days=1)
NEA_STALE_WARNING_AGE = timedelta(days=7)
NEA_MIN_ROWS = 10000  # sanity check against saving an error page or a truncated download


all_minor_planets_source_stamp = None


def _file_stamp(file_path):
    try:
        st = os.stat(file_path)
        return st.st_ino, st.st_mtime_ns, st.st_size
    except FileNotFoundError:
        return None


def _mpc_source_stamp():
    # Changes whenever any elements file is replaced or appended to, in any process.
    return _file_stamp(MPCORB_EXCERPT_FILE), _file_stamp(NEA_FILE)


def _load_mpcorb_file(file_path):
    with load.open(file_path) as f:
        minor_planets = mpc.load_mpcorb_dataframe(f)
    minor_planets = minor_planets[~minor_planets.semimajor_axis_au.isnull()].copy()
    minor_planets['designation_packed'] = minor_planets['designation_packed'].astype(str).str.strip()
    return minor_planets


def get_all_mpc_minor_planets():
    """
    Elements of all known minor planets: the MPCORB excerpt merged with MPC NEA.txt.
    NEA.txt (daily) takes precedence over the excerpt (weekly) for the same designation.
    Without NEA.txt only the excerpt is used. Reloaded when any source file changes.
    """
    global all_minor_planets, all_minor_planets_source_stamp
    source_stamp = _mpc_source_stamp()
    if all_minor_planets is not None and source_stamp != all_minor_planets_source_stamp:
        reset_minor_planets_cache()
    if all_minor_planets is None:
        all_minor_planets_source_stamp = source_stamp
        frames = []
        if source_stamp[1] is not None:
            frames.append(_load_mpcorb_file(NEA_FILE))
        frames.append(_load_mpcorb_file(MPCORB_EXCERPT_FILE))
        merged = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        merged = merged.drop_duplicates(subset='designation_packed', keep='first')
        merged['minor_planet_id'] = merged['designation_packed']
        all_minor_planets = merged.set_index('designation_packed', drop=False)
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


def _find_mpc_minor_planet_or_none(minor_planet):
    try:
        return find_mpc_minor_planet(minor_planet)
    except KeyError:
        return None


def get_mpc_minor_planet_position(mpc_minor_planet, dt, observer_lat=None, observer_lon=None, observer_elevation=0.0):
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    t = ts.from_datetime(dt.replace(tzinfo=utc))
    skf_mplanet = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)

    observer = earth
    if observer_lat is not None and observer_lon is not None:
        observer = earth + wgs84.latlon(
            latitude_degrees=observer_lat,
            longitude_degrees=observer_lon,
            elevation_m=observer_elevation,
        )

    ra_ang, dec_ang, _ = observer.at(t).observe(skf_mplanet).radec()
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
def _get_minor_planet_cached(
        minor_planet_mpc_designation: str,
        dt: datetime,
        observer_lat: float | None,
        observer_lon: float | None,
        observer_elevation: float):
    mpc_minor_planet = find_mpc_minor_planet(minor_planet_mpc_designation)
    ra_ang, dec_ang = get_mpc_minor_planet_position(
        mpc_minor_planet,
        dt,
        observer_lat=observer_lat,
        observer_lon=observer_lon,
        observer_elevation=observer_elevation,
    )
    return ra_ang.radians, dec_ang.radians


def get_minor_planet_radec(minor_planet, dt: datetime, observer_lat=None, observer_lon=None, observer_elevation=0.0):
    # Check for a changed elements file before the cache can return an old position.
    get_all_mpc_minor_planets()
    if getattr(minor_planet, 'is_neo', False):
        # A close NEA moves up to ~1.4"/s; the 300 s cache step would shift it by minutes of arc.
        dt = dt.astimezone(utc) if dt.tzinfo is not None else dt.replace(tzinfo=utc)
        ra_ang, dec_ang = get_mpc_minor_planet_position(
            find_mpc_minor_planet(minor_planet), dt,
            observer_lat=observer_lat, observer_lon=observer_lon, observer_elevation=observer_elevation,
        )
        return ra_ang.radians, dec_ang.radians
    normalized_dt = _normalize_to_300s(dt)
    return _get_minor_planet_cached(
        _get_minor_planet_mpc_designation(minor_planet),
        normalized_dt,
        round(float(observer_lat), 6) if observer_lat is not None else None,
        round(float(observer_lon), 6) if observer_lon is not None else None,
        round(float(observer_elevation), 1),
    )


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
        mpc_mplanet = _find_mpc_minor_planet_or_none(minor_planet)
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
        mpc_minor_planet = _find_mpc_minor_planet_or_none(minor_planet)
        if mpc_minor_planet is not None and _calculate_minor_planet_brightness(
                minor_planet, mpc_minor_planet, ts, sun, earth, t, earth_sun_distance):
            minor_planets.append(minor_planet)
        if show_progress:
            progress(i, len(mpc_minor_planets), 'Evaluating minor planet brightness...')
        elif i % 500 == 0:
            current_app.logger.info('Updated {} minor planets brightness.'.format(i))
        i += 1

    _save_minor_planets(minor_planets, show_progress, 'Saving minor planets...')
    current_app.logger.info('Minor planets\' brightnesses updated.')


def _calculate_minor_planet_brightness(minor_planet, mpc_minor_planet, ts, sun, earth, t, earth_sun_distance):
    body = sun + mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN)
    _, _, sun_body_distance = sun.at(t).observe(body).radec()
    _, _, earth_body_distance = earth.at(t).observe(body).apparent().radec()
    apparent_magnitude = _get_apparent_magnitude_hg(minor_planet.magnitude_H, minor_planet.magnitude_G,
                                                    earth_body_distance.au, sun_body_distance.au,
                                                    earth_sun_distance.au)
    if apparent_magnitude:
        minor_planet.eval_mag = apparent_magnitude
        return True
    return False


def update_minor_planets_elements_from_mpc(show_progress=False):
    """
    Copies current MPC elements, H/G and flags from the elements file into all DB rows,
    in one transaction. Cheap: no Skyfield computation. Position and brightness from
    the new elements are recomputed by the daily update at the low-traffic hour.
    """
    get_all_mpc_minor_planets()

    minor_planets = MinorPlanet.query.all()
    missing = 0
    try:
        for i, minor_planet in enumerate(minor_planets, start=1):
            mpc_minor_planet = _find_mpc_minor_planet_or_none(minor_planet)
            if mpc_minor_planet is None:
                missing += 1
                continue
            assign_minor_planet_from_mpc_row(minor_planet, mpc_minor_planet)
            if show_progress:
                progress(i, len(minor_planets), 'Updating minor planets elements from MPC...')
        if show_progress:
            print('')
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if missing:
        current_app.logger.warning('{} minor planets not found in MPC elements file.'.format(missing))
    current_app.logger.info('Minor planets elements updated from MPC.')


def update_neo_positions(update_elements=False):
    """
    Recomputes position and brightness of near-Earth asteroids only (hundreds of rows,
    cheap enough to run hourly). With update_elements also copies their current elements
    from the elements file (NEA.txt takes precedence) into the DB.
    """
    get_all_mpc_minor_planets()

    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    t = ts.now()
    sun, earth = eph['sun'], eph['earth']
    _, _, earth_sun_distance = earth.at(t).observe(sun).apparent().radec()
    constellation_at = load_constellation_map()

    neos = MinorPlanet.query.filter(MinorPlanet.is_neo.is_(True)).all()
    updated = 0
    try:
        for minor_planet in neos:
            mpc_minor_planet = _find_mpc_minor_planet_or_none(minor_planet)
            if mpc_minor_planet is None:
                continue
            if update_elements:
                assign_minor_planet_from_mpc_row(minor_planet, mpc_minor_planet)
            _calculate_minor_planet_current_values(minor_planet, mpc_minor_planet, ts, eph, t, constellation_at)
            _calculate_minor_planet_brightness(minor_planet, mpc_minor_planet, ts, sun, earth, t, earth_sun_distance)
            updated += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    current_app.logger.info('Updated {} of {} near-Earth asteroids.'.format(updated, len(neos)))


def _mpcorb_file_is_fresh(file_path):
    if not os.path.exists(file_path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=utc)
    return datetime.now(tz=utc) - mtime <= MPCORB_MAX_AGE


def ensure_nea_file(force_reload=False):
    """
    Downloads MPC NEA.txt when older than a day. On failure keeps the last downloaded
    file (warning when older than a week). Returns the file path, or None when no file exists.
    """
    if not force_reload and _mpcorb_file_is_fresh(NEA_FILE):
        return NEA_FILE

    data_dir = os.path.dirname(NEA_FILE) or '.'
    os.makedirs(data_dir, exist_ok=True)
    tmp_file_path = os.path.join(data_dir, 'NEA.txt.{}.tmp'.format(uuid.uuid4().hex))
    try:
        response = requests.get(NEA_URL, timeout=120)
        response.raise_for_status()
        rows = len(mpc.load_mpcorb_dataframe(io.BytesIO(response.content)))
        if rows < NEA_MIN_ROWS:
            raise RuntimeError('NEA.txt has only {} rows.'.format(rows))
        with open(tmp_file_path, 'wb') as f:
            f.write(response.content)
        os.replace(tmp_file_path, NEA_FILE)
        current_app.logger.info('File NEA.txt updated, {} rows.'.format(rows))
    except Exception:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        if not os.path.exists(NEA_FILE):
            current_app.logger.exception('Download NEA.txt failed and no previous file exists.')
            return None
        age = datetime.now(tz=utc) - datetime.fromtimestamp(os.path.getmtime(NEA_FILE), tz=utc)
        if age > NEA_STALE_WARNING_AGE:
            current_app.logger.exception('Download NEA.txt failed, using file {} days old.'.format(age.days))
        else:
            current_app.logger.warning('Download NEA.txt failed, using previous file.', exc_info=True)
    return NEA_FILE


def ensure_full_mpcorb_file(force_reload=False):
    if not force_reload and _mpcorb_file_is_fresh(MPCORB_FULL_GZ_FILE):
        return MPCORB_FULL_GZ_FILE

    data_dir = os.path.dirname(MPCORB_FULL_GZ_FILE)
    os.makedirs(data_dir, exist_ok=True)
    tmp_file_path = os.path.join(data_dir, 'MPCORB.DAT.{}.gz.tmp'.format(uuid.uuid4().hex))
    try:
        response = requests.get(MPCORB_URL, stream=True)
        if response.status_code != 200:
            raise RuntimeError('Download MPCORB.DAT.gz failed. url={}'.format(MPCORB_URL))
        with open(tmp_file_path, 'wb') as f:
            f.write(response.raw.read())
        os.rename(tmp_file_path, MPCORB_FULL_GZ_FILE)
    except Exception:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        if os.path.exists(MPCORB_FULL_GZ_FILE):
            current_app.logger.warning('Using stale MPCORB.DAT.gz because refresh failed.', exc_info=True)
            return MPCORB_FULL_GZ_FILE
        raise
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


MPCORB_EXCERPT_FIRST_ROW = 44      # first data row after the MPCORB.DAT header
MPCORB_EXCERPT_LAST_ROW = 10042    # first ~10k numbered minor planets


def rebuild_mpcorb_excerpt(mpcorb_file, extra_mpc_designations):
    """
    Writes the excerpt (first ~10k numbered minor planets plus extra_mpc_designations)
    to a temporary file and moves it into place only when complete, so other processes
    never load a partial excerpt. Returns the extra designations not found.
    """
    needed_designations = {str(x).strip() for x in extra_mpc_designations if x}
    data_dir = os.path.dirname(MPCORB_EXCERPT_FILE) or '.'
    tmp_file_path = os.path.join(data_dir, 'MPCORB.9999.DAT.{}.tmp'.format(uuid.uuid4().hex))
    opener = gzip.open if mpcorb_file.endswith('.gz') else open
    try:
        with opener(mpcorb_file, 'rt', encoding='ascii', errors='ignore') as src, \
                open(tmp_file_path, 'w', encoding='ascii') as out:
            for row, line in enumerate(src, start=1):
                if row < MPCORB_EXCERPT_FIRST_ROW:
                    continue
                if not line.endswith('\n'):
                    line += '\n'
                mpc_designation = line[:7].strip()
                if row <= MPCORB_EXCERPT_LAST_ROW:
                    out.write(line)
                    needed_designations.discard(mpc_designation)
                elif not needed_designations:
                    break
                elif mpc_designation in needed_designations:
                    out.write(line)
                    needed_designations.remove(mpc_designation)
        os.replace(tmp_file_path, MPCORB_EXCERPT_FILE)
    except Exception:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        raise
    return needed_designations


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
