"""
Near-Earth asteroids: close approaches from the JPL CNEOS close-approach (CAD) API.

Approaches are fetched daily, filtered by a rough peak brightness estimate, and the
asteroids found in the elements files (MPC NEA.txt or the MPCORB excerpt) are imported
into minor_planets.
"""
import math
import re
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import requests
from flask import current_app
from skyfield.api import load
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from sqlalchemy import exists

from app import db
from app.models import (
    DB_UPDATE_NEO_KEY,
    MinorPlanet,
    NeoCloseApproach,
    NeoEphemerisSegment,
    Observation,
    ObservedListItem,
    SessionPlanItem,
    UserObjectListItem,
)
from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.commons.horizons_utils import HybridMinorPlanetBody, build_verified_ephemeris, horizons_command
from app.commons.minor_planet_utils import (
    ensure_nea_file,
    get_all_mpc_minor_planets,
    sun_earth_body_distances,
    update_neo_positions,
)
from app.commons.neo_ephemeris_utils import (
    datetime_to_jd,
    delete_obsolete_neo_ephemeris_query,
    load_neo_ephemeris,
    replace_neo_ephemeris,
)
from imports.import_minor_planets import assign_minor_planet_from_mpc_row, _int_designation_from_mpc_row

CAD_API_URL = 'https://ssd-api.jpl.nasa.gov/cad.api'
CAD_REQUIRED_FIELDS = ('des', 'orbit_id', 'jd', 'dist', 'dist_min', 'dist_max', 'v_rel', 't_sigma_f', 'h')

# Like the van Buitenen NEO list: the next 3 months.
NEO_APPROACH_DAYS = 90
# Not only very close passes: large asteroids are bright also from a few tenths of au.
NEO_APPROACH_DIST_MAX_AU = 0.3
NEO_PEAK_MAG_LIMIT = 18.0
# The rough estimate ignores the phase angle, so it is brighter than the computed peak
# (with r ~ 1 AU); preselect with a margin and decide by the computed peak.
NEO_PREFILTER_MAG_MARGIN = 0.5
# The brightest moment is searched within +-30 days of the closest approach (for distant
# approaches the phase angle, not the distance, decides), refined in steps:
# (half window, step) in minutes.
NEO_PEAK_SEARCH_STAGES = ((30 * 24 * 60, 6 * 60), (6 * 60, 15), (15, 1))
# Approaches closer than this always get a Horizons ephemeris before the final filter: there the
# MPC two-body orbit can be wrong by magnitudes (Earth's pull during the flyby; e.g. 2023 BU
# 15.1 mag by MPC vs 11.6 by Horizons), so it must not decide.
NEO_HORIZONS_ALWAYS_DIST_AU = 0.05
# Farther approaches: preselected by the peak from the stored ephemeris or the MPC orbit with
# this margin. There the MPC position error (minutes of arc, thousands of km at tenths of au)
# changes the brightness by hundredths of a magnitude.
NEO_HORIZONS_MAG_MARGIN = 0.3
# Horizons coverage around now (listing and positions) and around each approach (peak search
# +-30 days, plus a day for light time).
NEO_EPHEMERIS_PAST = timedelta(days=2)
NEO_EPHEMERIS_FUTURE = timedelta(days=91)
NEO_EPHEMERIS_APPROACH_MARGIN = timedelta(days=31)
# Past approaches are not shown anywhere; keep them a while, then delete.
NEO_APPROACH_HISTORY = timedelta(days=30)
# Asteroids imported by the NEA update are deleted again when unused for this long.
NEO_IMPORT_RETENTION = timedelta(days=30)
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


def apparent_magnitude_hg(h, g, r_au, delta_au, earth_sun_au):
    """Vectorized IAU H, G apparent magnitude (same model as minor_planet_utils._get_apparent_magnitude_hg)."""
    r_au = np.asarray(r_au, dtype=float)
    delta_au = np.asarray(delta_au, dtype=float)
    earth_sun_au = np.asarray(earth_sun_au, dtype=float)
    cos_phase = np.clip((r_au ** 2 + delta_au ** 2 - earth_sun_au ** 2) / (2.0 * r_au * delta_au), -1.0, 1.0)
    tan_half_phase = np.tan(np.arccos(cos_phase) / 2.0)
    phi1 = np.exp(-3.33 * tan_half_phase ** 0.63)
    phi2 = np.exp(-1.87 * tan_half_phase ** 1.22)
    with np.errstate(divide='ignore', invalid='ignore'):
        return h + 5.0 * np.log10(r_au * delta_au) - 2.5 * np.log10((1.0 - g) * phi1 + g * phi2)


_sun_earth_body_distances = sun_earth_body_distances


def _magnitudes_at(body, base_time, offsets_seconds, ts, sun, earth, h, g):
    t = ts.utc(base_time.year, base_time.month, base_time.day, base_time.hour, base_time.minute,
               base_time.second + base_time.microsecond / 1e6 + offsets_seconds)
    r, delta, earth_sun = _sun_earth_body_distances(body, t, sun, earth)
    return t, apparent_magnitude_hg(h, g, r, delta, earth_sun)


def compute_peak_brightness(mpc_row, approach_time, ts, eph, segments=None):
    """
    Brightest geocentric apparent magnitude within +-30 days of approach_time (NEO_PEAK_SEARCH_STAGES)
    with the H, G phase model, from the Horizons segments where they cover the time and the MPC
    orbit (two-body) elsewhere. Returns (peak_mag, peak_time UTC naive) or (None, None) without a
    usable H.
    """
    h = mpc_row['magnitude_H']
    if h is None or not np.isfinite(h):
        return None, None
    g = mpc_row['magnitude_G']
    g = 0.15 if g is None or not np.isfinite(g) else float(g)
    sun, earth = eph['sun'], eph['earth']
    orbit = mpc.mpcorb_orbit(mpc_row, ts, GM_SUN)
    body = HybridMinorPlanetBody(earth, sun, orbit, segments) if segments else sun + orbit

    best = 0.0
    for half_window, step in NEO_PEAK_SEARCH_STAGES:
        offsets = best + np.arange(-half_window, half_window + step, step) * 60.0
        t, mags = _magnitudes_at(body, approach_time, offsets, ts, sun, earth, float(h), g)
        if not np.isfinite(mags).any():
            return None, None
        i = int(np.nanargmin(mags))
        best = offsets[i]
    return float(mags[i]), t[i].utc_datetime().replace(tzinfo=None, microsecond=0)


def build_designation_index(mpc_minor_planets):
    """Maps CAD designations ('433', '2026 UK') to packed MPC designations."""
    index = {}
    for packed, designation in zip(mpc_minor_planets['designation_packed'], mpc_minor_planets['designation']):
        designation = str(designation).strip()
        match = re.match(r'^\((\d+)\)', designation)
        index.setdefault(match.group(1) if match else designation, packed)
    return index


def _get_or_create_minor_planet(mpc_row, now):
    mpc_designation = str(mpc_row['designation_packed']).strip()
    minor_planet = MinorPlanet.query.filter_by(mpc_designation=mpc_designation).first()
    if minor_planet is None:
        int_designation = _int_designation_from_mpc_row(mpc_row)
        if int_designation is not None:
            minor_planet = MinorPlanet.query.filter_by(int_designation=int_designation).first()
    if minor_planet is None:
        # Marked as imported by this update, so cleanup_neo_data() may delete it once unused.
        minor_planet = MinorPlanet(neo_imported_at=now)
        db.session.add(minor_planet)
    assign_minor_planet_from_mpc_row(minor_planet, mpc_row)
    return minor_planet


def _provisional_designation(mpc_row):
    designation = str(mpc_row['designation'] or '').strip()
    return None if designation.startswith('(') else designation


def fetch_neo_ephemeris(mpc_row, approach_times, now):
    """
    Verified Horizons ephemeris segments of an asteroid covering now and +-31 days around its
    approaches (see NEO_EPHEMERIS_*). Raises on Horizons failures.
    """
    start = min(now - NEO_EPHEMERIS_PAST, min(approach_times) - NEO_EPHEMERIS_APPROACH_MARGIN)
    stop = max(now + NEO_EPHEMERIS_FUTURE, max(approach_times) + NEO_EPHEMERIS_APPROACH_MARGIN)
    command = horizons_command(int_designation=_int_designation_from_mpc_row(mpc_row),
                               designation=_provisional_designation(mpc_row))
    # JD of UTC is used as TDB: the 69 s difference does not matter for the coverage window.
    return build_verified_ephemeris(command, datetime_to_jd(start), datetime_to_jd(stop))


def _stored_ephemeris(mpc_row):
    minor_planet = MinorPlanet.query.filter_by(mpc_designation=str(mpc_row['designation_packed']).strip()).first()
    return load_neo_ephemeris(minor_planet.id)[0] if minor_planet is not None else []


def store_close_approaches(approaches, window_start, days=NEO_APPROACH_DAYS, mag_limit=NEO_PEAK_MAG_LIMIT,
                           fetch_ephemeris=None):
    """
    Replaces stored approaches in [window_start, window_start + days) with the given ones whose
    peak brightness passes mag_limit, importing their asteroids and their Horizons ephemerides.
    Order: rough estimate and MPC orbit peak preselect the candidates (with margins), Horizons
    ephemerides are downloaded for them, the peak is recomputed with Horizons and only then
    filtered; the database is written in one transaction at the end. If Horizons fails for an
    asteroid, its previously stored ephemeris (if any) is kept and used.
    Approaches before window_start stay as history.
    """
    fetch_ephemeris = fetch_ephemeris or fetch_neo_ephemeris
    window_end = window_start + timedelta(days=days)
    mpc_minor_planets = get_all_mpc_minor_planets()
    index = build_designation_index(mpc_minor_planets)
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')

    def peak(mpc_row, approach_time, segments):
        try:
            return compute_peak_brightness(mpc_row, approach_time, ts, eph, segments=segments)
        except Exception:
            current_app.logger.exception('Peak brightness of {} failed.'.format(mpc_row['designation']))
            return None, None

    # 1. Candidates: no network, no writes.
    started = time.perf_counter()
    candidates = []
    unmatched = []
    for approach in approaches:
        if not window_start <= approach['approach_time'] < window_end:
            continue  # CAD bounds are TDB; drop the ~69 s overlap outside the window
        packed = index.get(approach['designation'])
        mpc_row = mpc_minor_planets.loc[packed] if packed is not None else None
        # Same H as the computed peak (MPC); CAD H only for asteroids without an orbit.
        h = approach['h']
        if mpc_row is not None and mpc_row['magnitude_H'] is not None and np.isfinite(mpc_row['magnitude_H']):
            h = float(mpc_row['magnitude_H'])
        est_peak_mag = estimate_peak_mag(h, approach['dist_au'])
        if est_peak_mag is None or est_peak_mag > mag_limit + NEO_PREFILTER_MAG_MARGIN:
            continue
        peak_mag = peak_time = None
        if mpc_row is not None:
            # The stored Horizons ephemeris (if any) already here, the MPC orbit otherwise.
            peak_mag, peak_time = peak(mpc_row, approach['approach_time'], _stored_ephemeris(mpc_row) or None)
            if (approach['dist_au'] >= NEO_HORIZONS_ALWAYS_DIST_AU and peak_mag is not None
                    and peak_mag > mag_limit + NEO_HORIZONS_MAG_MARGIN):
                continue
        elif est_peak_mag > mag_limit:
            continue
        candidates.append({'approach': approach, 'packed': packed, 'mpc_row': mpc_row,
                           'est_peak_mag': est_peak_mag, 'peak_mag': peak_mag, 'peak_time': peak_time})
    mpc_seconds = time.perf_counter() - started

    # 2. Horizons ephemerides of the candidates, before the final filter.
    started = time.perf_counter()
    fetched = {}  # packed -> new segments
    segments_for_peak = {}
    for packed in dict.fromkeys(c['packed'] for c in candidates if c['packed'] is not None):
        items = [c for c in candidates if c['packed'] == packed]
        try:
            fetched[packed] = fetch_ephemeris(items[0]['mpc_row'], [c['approach']['approach_time'] for c in items],
                                              window_start)
            segments_for_peak[packed] = fetched[packed]
        except Exception:
            current_app.logger.exception('Horizons ephemeris of {} failed; keeping the stored one.'.format(
                items[0]['mpc_row']['designation']))
            segments_for_peak[packed] = _stored_ephemeris(items[0]['mpc_row'])
    horizons_seconds = time.perf_counter() - started

    # 3. Final peak (Horizons where available) and filter.
    kept = []
    for c in candidates:
        segments = segments_for_peak.get(c['packed'])
        if segments:
            peak_mag, peak_time = peak(c['mpc_row'], c['approach']['approach_time'], segments)
            if peak_mag is not None:
                c['peak_mag'], c['peak_time'] = peak_mag, peak_time
        if (c['peak_mag'] if c['peak_mag'] is not None else c['est_peak_mag']) <= mag_limit:
            kept.append(c)

    # 4. One transaction.
    try:
        minor_planets = {}
        new_rows = []
        for c in kept:
            minor_planet = None
            if c['packed'] is not None:
                minor_planet = minor_planets.get(c['packed'])
                if minor_planet is None:
                    minor_planet = minor_planets[c['packed']] = _get_or_create_minor_planet(c['mpc_row'], window_start)
            else:
                unmatched.append(c['approach']['designation'])
            new_rows.append(NeoCloseApproach(minor_planet=minor_planet, est_peak_mag=c['est_peak_mag'],
                                             peak_mag=c['peak_mag'], peak_time=c['peak_time'], **c['approach']))
        db.session.flush()
        for packed, minor_planet in minor_planets.items():
            if fetched.get(packed):
                replace_neo_ephemeris(minor_planet.id, fetched[packed], window_start)

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
    current_app.logger.info(
        'Stored {} NEA close approaches of {} candidates; MPC peaks {:.1f} s, Horizons ephemerides of {} '
        'asteroids ({} failed) {:.1f} s.'.format(len(new_rows), len(candidates), mpc_seconds, len(segments_for_peak),
                                                 len(segments_for_peak) - len(fetched), horizons_seconds))
    return new_rows


def cleanup_neo_data(now):
    """
    Deletes approaches older than NEO_APPROACH_HISTORY and asteroids imported by the NEA update
    more than NEO_IMPORT_RETENTION ago that nothing references any more (no approach, observation,
    observed list, user list or session plan item). Rows from the initial import or a user search
    (neo_imported_at null) are never deleted. Also deletes Horizons ephemeris segments that ended
    or were not refreshed for a long time, and those of the deleted asteroids (an ephemeris alone
    does not keep an asteroid). One transaction.
    """
    try:
        deleted_approaches = NeoCloseApproach.query \
            .filter(NeoCloseApproach.approach_time < now - NEO_APPROACH_HISTORY) \
            .delete(synchronize_session=False)
        deleted_segments = delete_obsolete_neo_ephemeris_query(now).delete(synchronize_session=False)
        unused = MinorPlanet.query.filter(
            MinorPlanet.neo_imported_at.isnot(None),
            MinorPlanet.neo_imported_at < now - NEO_IMPORT_RETENTION,
            ~exists().where(NeoCloseApproach.minor_planet_id == MinorPlanet.id),
            ~exists().where(Observation.minor_planet_id == MinorPlanet.id),
            ~exists().where(ObservedListItem.minor_planet_id == MinorPlanet.id),
            ~exists().where(UserObjectListItem.minor_planet_id == MinorPlanet.id),
            ~exists().where(SessionPlanItem.minor_planet_id == MinorPlanet.id),
        )
        unused_ids = [minor_planet_id for (minor_planet_id,) in unused.with_entities(MinorPlanet.id)]
        deleted_minor_planets = 0
        if unused_ids:
            deleted_segments += NeoEphemerisSegment.query \
                .filter(NeoEphemerisSegment.minor_planet_id.in_(unused_ids)).delete(synchronize_session=False)
            deleted_minor_planets = MinorPlanet.query \
                .filter(MinorPlanet.id.in_(unused_ids)).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    current_app.logger.info('Deleted {} old NEA close approaches, {} unused imported asteroids and {} ephemeris '
                            'segments.'.format(deleted_approaches, deleted_minor_planets, deleted_segments))
    return deleted_approaches, deleted_minor_planets


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
    cleanup_neo_data(window_start)
    return True
