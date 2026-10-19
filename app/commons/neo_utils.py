"""
Near-Earth asteroids: close approaches from the JPL CNEOS close-approach (CAD) API.

Approaches are fetched daily, filtered by a rough peak brightness estimate, and the
asteroids found in the elements files (MPC NEA.txt or the MPCORB excerpt) are imported
into minor_planets.
"""
import math
import re
from datetime import datetime, timedelta, timezone

import requests
from flask import current_app
from skyfield.api import load

from app import db
from app.models import DB_UPDATE_NEO_KEY, MinorPlanet, NeoCloseApproach
from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.commons.minor_planet_utils import ensure_nea_file, get_all_mpc_minor_planets, update_neo_positions
from imports.import_minor_planets import assign_minor_planet_from_mpc_row, _int_designation_from_mpc_row

CAD_API_URL = 'https://ssd-api.jpl.nasa.gov/cad.api'
CAD_REQUIRED_FIELDS = ('des', 'orbit_id', 'jd', 'dist', 'dist_min', 'dist_max', 'v_rel', 't_sigma_f', 'h')

NEO_APPROACH_DAYS = 60
NEO_APPROACH_DIST_MAX_AU = 0.05
NEO_PEAK_MAG_LIMIT = 18.0
# Daily job: the claim must expire before the next run (interval minus jitter).
NEO_UPDATE_LOCK_DURATION = timedelta(hours=20)


class CloseApproachSourceError(Exception):
    """The CAD API failed or returned data that cannot be trusted; keep the stored approaches."""


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _optional_float(value):
    return None if value is None or value == '' else float(value)


def parse_close_approaches(payload, ts=None):
    """
    Parses a CAD API response into dicts. Raises CloseApproachSourceError for anything
    unexpected; a valid response with count 0 gives an empty list.
    """
    if not isinstance(payload, dict) or 'signature' not in payload or 'count' not in payload:
        raise CloseApproachSourceError('Unexpected CAD response: {}'.format(str(payload)[:200]))
    try:
        count = int(payload['count'])
    except (TypeError, ValueError) as e:
        raise CloseApproachSourceError('Invalid CAD count: {!r}'.format(payload['count'])) from e
    if count == 0:
        return []

    fields = payload.get('fields') or []
    data = payload.get('data') or []
    missing_fields = [f for f in CAD_REQUIRED_FIELDS if f not in fields]
    if missing_fields:
        raise CloseApproachSourceError('CAD response is missing fields {}'.format(missing_fields))
    if len(data) != count:
        raise CloseApproachSourceError('CAD count {} does not match {} rows'.format(count, len(data)))

    ts = ts or load.timescale(builtin=True)
    idx = {name: i for i, name in enumerate(fields)}
    approaches = []
    for row in data:
        try:
            designation = str(row[idx['des']]).strip()
            if not designation:
                raise ValueError('empty designation')
            # CAD times are TDB, not UTC (they differ by about 69 s).
            approach_time = ts.tdb_jd(float(row[idx['jd']])).utc_datetime().replace(tzinfo=None)
            approaches.append({
                'designation': designation,
                'approach_time': approach_time,
                'dist_au': float(row[idx['dist']]),
                'dist_min_au': _optional_float(row[idx['dist_min']]),
                'dist_max_au': _optional_float(row[idx['dist_max']]),
                'v_rel_kms': _optional_float(row[idx['v_rel']]),
                'h': _optional_float(row[idx['h']]),
                't_sigma': None if row[idx['t_sigma_f']] is None else str(row[idx['t_sigma_f']])[:16],
                'orbit_id': None if row[idx['orbit_id']] is None else str(row[idx['orbit_id']])[:16],
            })
        except (IndexError, TypeError, ValueError) as e:
            raise CloseApproachSourceError('Invalid CAD row {!r}'.format(row)) from e
    return approaches


def _cad_datetime(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S')


def fetch_close_approaches(window_start, days=NEO_APPROACH_DAYS, dist_max_au=NEO_APPROACH_DIST_MAX_AU):
    # Exact bounds: date-min=now means today from midnight, which would return approaches
    # before window_start that store_close_approaches never replaces.
    params = {
        'date-min': _cad_datetime(window_start),
        'date-max': _cad_datetime(window_start + timedelta(days=days)),
        'dist-max': str(dist_max_au),
        'nea': 'true',  # asteroids only; 'neo' would include near-Earth comets
        'fullname': 'true',
    }
    try:
        response = requests.get(CAD_API_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as e:
        raise CloseApproachSourceError('CAD API request failed: {}'.format(e)) from e
    return parse_close_approaches(payload)


def estimate_peak_mag(h, dist_au):
    """
    Rough apparent magnitude at closest approach: H + 5 log10(r * delta) with r ~ 1 AU and
    no phase correction. Used only to pick approaches worth showing.
    """
    if h is None or dist_au is None or dist_au <= 0:
        return None
    return h + 5.0 * math.log10(dist_au)


def build_designation_index(mpc_minor_planets):
    """Maps CAD designations ('433', '2026 UK') to packed MPC designations."""
    index = {}
    for packed, designation in zip(mpc_minor_planets['designation_packed'], mpc_minor_planets['designation']):
        designation = str(designation).strip()
        match = re.match(r'^\((\d+)\)', designation)
        index.setdefault(match.group(1) if match else designation, packed)
    return index


def _get_or_create_minor_planet(mpc_row):
    mpc_designation = str(mpc_row['designation_packed']).strip()
    minor_planet = MinorPlanet.query.filter_by(mpc_designation=mpc_designation).first()
    if minor_planet is None:
        int_designation = _int_designation_from_mpc_row(mpc_row)
        if int_designation is not None:
            minor_planet = MinorPlanet.query.filter_by(int_designation=int_designation).first()
    if minor_planet is None:
        minor_planet = MinorPlanet()
        db.session.add(minor_planet)
    assign_minor_planet_from_mpc_row(minor_planet, mpc_row)
    return minor_planet


def store_close_approaches(approaches, window_start, days=NEO_APPROACH_DAYS, mag_limit=NEO_PEAK_MAG_LIMIT):
    """
    Replaces stored approaches in [window_start, window_start + days) with the given ones
    that pass mag_limit, importing their asteroids, all in one transaction.
    Approaches before window_start stay as history.
    """
    window_end = window_start + timedelta(days=days)
    mpc_minor_planets = get_all_mpc_minor_planets()
    index = build_designation_index(mpc_minor_planets)

    try:
        new_rows = []
        unmatched = []
        for approach in approaches:
            if not window_start <= approach['approach_time'] < window_end:
                continue  # CAD bounds are TDB; drop the ~69 s overlap outside the window
            est_peak_mag = estimate_peak_mag(approach['h'], approach['dist_au'])
            if est_peak_mag is None or est_peak_mag > mag_limit:
                continue
            minor_planet = None
            packed = index.get(approach['designation'])
            if packed is not None:
                minor_planet = _get_or_create_minor_planet(mpc_minor_planets.loc[packed])
            else:
                unmatched.append(approach['designation'])
            new_rows.append(NeoCloseApproach(minor_planet=minor_planet, est_peak_mag=est_peak_mag, **approach))

        NeoCloseApproach.query.filter(
            NeoCloseApproach.approach_time >= window_start,
            NeoCloseApproach.approach_time < window_end,
        ).delete(synchronize_session=False)
        db.session.add_all(new_rows)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if unmatched:
        current_app.logger.warning('NEA close approaches without elements: {}'.format(', '.join(unmatched)))
    current_app.logger.info('Stored {} NEA close approaches.'.format(len(new_rows)))
    return new_rows


def update_neos(force=False):
    """
    Daily update: NEA.txt, close approaches from CNEOS, then NEA elements, positions and brightness.
    Claims DB_UPDATE_NEO_KEY first, so the scheduler and the CLI never run it concurrently;
    force skips the claim (for a lock left by a crashed run). Returns False when not run.
    """
    if not force and not ask_dbupdate_permit(DB_UPDATE_NEO_KEY, NEO_UPDATE_LOCK_DURATION):
        current_app.logger.info('NEA update skipped: already running or done recently.')
        return False
    # Always download: with a 24 h freshness check a run starting a few seconds earlier
    # than yesterday's would skip the download. The file is in place before the DB writes.
    ensure_nea_file(force_reload=True)
    window_start = _utcnow()
    try:
        approaches = fetch_close_approaches(window_start)
    except CloseApproachSourceError:
        current_app.logger.exception('Fetching NEA close approaches failed; keeping stored data.')
    else:
        store_close_approaches(approaches, window_start)
    update_neo_positions(update_elements=True)
    return True
