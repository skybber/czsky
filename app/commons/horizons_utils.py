"""
Precise ephemerides of near-Earth asteroids from JPL Horizons.

Geocentric geometric state vectors (ICRF, TDB, au and au/day) are downloaded in a regular
table and interpolated with cubic Hermite polynomials. The table step is chosen per object:
the interpolation is checked against Horizons at the midpoints between the nodes and refined
where it exceeds the tolerance (see docs/plans/neo-horizons-ephemeris.md).

Geocentric (not barycentric) vectors: the app takes the Earth from de421.bsp, Horizons from
DE441, and with geocentric vectors their difference does not enter the asteroid position
relative to the Earth, which is what has to be precise.
"""
import hashlib
import re
from dataclasses import dataclass, field

import numpy as np
import requests
from skyfield.vectorlib import VectorFunction

HORIZONS_API_URL = 'https://ssd.jpl.nasa.gov/api/horizons.api'
HORIZONS_VECTOR_PARAMS = {
    'format': 'text',
    'OBJ_DATA': 'YES',  # the header carries the orbit solution id
    'MAKE_EPHEM': 'YES',
    'EPHEM_TYPE': 'VECTORS',
    'CENTER': '500@399',  # geocenter
    'REF_SYSTEM': 'ICRF',
    'REF_PLANE': 'FRAME',  # equatorial ICRF axes; the vector default is the ecliptic
    'VEC_CORR': 'NONE',  # geometric; Skyfield applies light time in observe()
    'TIME_TYPE': 'TDB',
    'OUT_UNITS': 'AU-D',
    'VEC_TABLE': '2',  # position and velocity
    'CSV_FORMAT': 'YES',
}
HORIZONS_MAX_ROWS = 90000  # Horizons refuses outputs over ~90 024 lines
HORIZONS_TIMEOUT_SECONDS = 120

AU_KM = 149597870.7
EARTH_RADIUS_AU = 6378.137 / AU_KM
ARCSEC_PER_RADIAN = 206264.80624709636
MINUTES_PER_DAY = 1440.0

# Interpolation must match Horizons within this angle, seen from the worst place on the Earth.
NEO_EPHEMERIS_TOLERANCE_ARCSEC = 1.0
# Table steps tried in turn where the previous one fails the check.
NEO_EPHEMERIS_STEPS_MINUTES = (60.0, 15.0, 5.0, 1.0)


class HorizonsError(Exception):
    """Horizons failed or returned something that is not a usable vector table."""


@dataclass
class VectorTable:
    jd_tdb: np.ndarray  # (n,)
    states: np.ndarray  # (n, 6): x, y, z [au], vx, vy, vz [au/day]
    orbit_solution: str


def horizons_command(int_designation=None, designation=None):
    """Horizons COMMAND for a small body: '433;' for numbered, 'DES=2026 UK;' for provisional."""
    if int_designation is not None:
        return '{};'.format(int(int_designation))
    if designation:
        return 'DES={};'.format(str(designation).strip())
    raise ValueError('Minor planet without a designation')


def _jd_param(jd):
    return "'JD {:.9f}'".format(jd)


def parse_vector_table(text):
    """Parses a Horizons VECTORS CSV response (VEC_TABLE=2)."""
    if '$$SOE' not in text or '$$EOE' not in text:
        message = ' '.join(line.strip() for line in text.splitlines() if line.strip())[:300]
        raise HorizonsError('Horizons returned no ephemeris: {}'.format(message))
    body = text.split('$$SOE', 1)[1].split('$$EOE', 1)[0]
    rows = []
    for line in body.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(',')]
        try:
            rows.append([float(parts[0])] + [float(x) for x in parts[2:8]])
        except (IndexError, ValueError) as e:
            raise HorizonsError('Invalid Horizons vector row: {!r}'.format(line[:120])) from e
    if len(rows) < 2:
        raise HorizonsError('Horizons returned {} vector rows'.format(len(rows)))
    table = np.array(rows)
    if not np.all(np.diff(table[:, 0]) > 0):
        raise HorizonsError('Horizons vector times are not increasing')
    match = re.search(r'soln ref\.\s*=\s*([^,\s]+)', text)
    return VectorTable(jd_tdb=table[:, 0], states=table[:, 1:7], orbit_solution=match.group(1) if match else '')


def vector_request_params(command, start_jd, stop_jd, step_minutes):
    rows = int((stop_jd - start_jd) * MINUTES_PER_DAY / step_minutes) + 1
    if rows > HORIZONS_MAX_ROWS:
        raise ValueError('Horizons request too long: {} rows'.format(rows))
    params = dict(HORIZONS_VECTOR_PARAMS)
    params.update({
        'COMMAND': "'{}'".format(command),
        'START_TIME': _jd_param(start_jd),
        'STOP_TIME': _jd_param(stop_jd),
        'STEP_SIZE': "'{:g} m'".format(step_minutes),
    })
    return params


def request_vector_text(command, start_jd, stop_jd, step_minutes):
    """Raw Horizons response text for a geocentric VECTORS request."""
    params = vector_request_params(command, start_jd, stop_jd, step_minutes)
    try:
        response = requests.get(HORIZONS_API_URL, params=params, timeout=HORIZONS_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HorizonsError('Horizons request failed: {}'.format(e)) from e
    return response.text


def fetch_vectors(command, start_jd, stop_jd, step_minutes):
    """Geocentric geometric state vectors from start_jd to stop_jd (TDB) in step_minutes."""
    return parse_vector_table(request_vector_text(command, start_jd, stop_jd, step_minutes))


def hermite_interpolate(start_jd, step_days, states, jd):
    """
    Cubic Hermite interpolation of positions (and their derivative, the velocity) in a regular
    table. Returns (positions (3, m) au, velocities (3, m) au/day); jd must be inside the table.
    """
    jd = np.atleast_1d(np.asarray(jd, dtype=float))
    u = (jd - start_jd) / step_days
    i = np.clip(np.floor(u).astype(int), 0, len(states) - 2)
    s = (u - i)[:, None]
    p0, v0 = states[i, :3], states[i, 3:] * step_days
    p1, v1 = states[i + 1, :3], states[i + 1, 3:] * step_days
    s2, s3 = s * s, s * s * s
    position = (2 * s3 - 3 * s2 + 1) * p0 + (s3 - 2 * s2 + s) * v0 + (-2 * s3 + 3 * s2) * p1 + (s3 - s2) * v1
    velocity = ((6 * s2 - 6 * s) * p0 + (3 * s2 - 4 * s + 1) * v0 + (-6 * s2 + 6 * s) * p1 + (3 * s2 - 2 * s) * v1) \
        / step_days
    return position.T, velocity.T


def interpolation_error_arcsec(interpolated, true_positions):
    """Angle of the position error seen from the worst place on the Earth's surface; arrays (3, m)."""
    error = np.linalg.norm(interpolated - true_positions, axis=0)
    distance = np.linalg.norm(true_positions, axis=0) - EARTH_RADIUS_AU
    return error / distance * ARCSEC_PER_RADIAN


@dataclass
class EphemerisSegment:
    start_jd: float  # TDB
    step_minutes: float
    states: np.ndarray  # (n, 6) geocentric, au and au/day
    # Interpolation checked against Horizons wherever this is the finest segment covering the time.
    verified: bool = False
    max_check_error_arcsec: float = None
    orbit_solution: str = ''
    children: list = field(default_factory=list, repr=False)

    @property
    def step_days(self):
        return self.step_minutes / MINUTES_PER_DAY

    @property
    def end_jd(self):
        return self.start_jd + (len(self.states) - 1) * self.step_days

    def covers(self, jd):
        jd = np.asarray(jd, dtype=float)
        return (jd >= self.start_jd) & (jd <= self.end_jd)

    def evaluate(self, jd):
        return hermite_interpolate(self.start_jd, self.step_days, self.states, jd)

    def revision(self):
        digest = hashlib.sha1()
        digest.update('{:.9f}|{:g}|{}'.format(self.start_jd, self.step_minutes, self.orbit_solution).encode())
        digest.update(np.ascontiguousarray(self.states, dtype='<f8').tobytes())
        return digest.hexdigest()[:16]


def _bad_runs(bad, gap=2):
    """Index runs of True values in bad, merging runs separated by at most gap False values."""
    runs = []
    for i in np.flatnonzero(bad):
        if runs and i - runs[-1][1] <= gap + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return runs


def build_verified_ephemeris(command, start_jd, stop_jd, fetch=fetch_vectors,
                             tolerance_arcsec=NEO_EPHEMERIS_TOLERANCE_ARCSEC,
                             steps_minutes=NEO_EPHEMERIS_STEPS_MINUTES):
    """
    Downloads the table for [start_jd, stop_jd] in the first step and checks the interpolation
    at the midpoints between the nodes (a second request offset by half a step). Where the error
    exceeds the tolerance, the surrounding interval is downloaded in the next finer step and
    checked the same way. Returns all segments (coarse first); a segment is verified when its
    own checks pass or every failing check is covered by a verified finer segment. Checks are
    samples, not a proof of the maximum error between them.
    """
    segments = []

    def build(start, stop, level):
        step = steps_minutes[level]
        step_days = step / MINUTES_PER_DAY
        nodes = fetch(command, start, stop, step)
        segment = EphemerisSegment(start_jd=float(nodes.jd_tdb[0]), step_minutes=step, states=nodes.states,
                                   orbit_solution=nodes.orbit_solution)
        segments.append(segment)
        checks = fetch(command, segment.start_jd + step_days / 2, segment.end_jd - step_days / 2, step)
        inside = segment.covers(checks.jd_tdb)
        position, _ = segment.evaluate(checks.jd_tdb[inside])
        errors = interpolation_error_arcsec(position, checks.states[inside, :3].T)
        segment.max_check_error_arcsec = float(errors.max()) if errors.size else 0.0
        bad = errors > tolerance_arcsec
        if not bad.any():
            segment.verified = True
            return segment
        if level + 1 >= len(steps_minutes):
            segment.verified = False
            return segment
        check_jd = checks.jd_tdb[inside]
        children_ok = True
        for first, last in _bad_runs(bad):
            sub_start = max(segment.start_jd, check_jd[first] - step_days)
            sub_stop = min(segment.end_jd, check_jd[last] + step_days)
            child = build(sub_start, sub_stop, level + 1)
            segment.children.append(child)
            children_ok = children_ok and child.verified
        segment.verified = children_ok
        return segment

    build(start_jd, stop_jd, 0)
    return segments


def finest_segment_index(segments, jd):
    """Per time, index of the covering segment with the smallest step, or -1 outside all segments."""
    jd = np.atleast_1d(np.asarray(jd, dtype=float))
    index = np.full(jd.shape, -1)
    best_step = np.full(jd.shape, np.inf)
    for i, segment in enumerate(segments):
        better = segment.covers(jd) & (segment.step_minutes < best_step)
        index[better] = i
        best_step[better] = segment.step_minutes
    return index


def evaluate_segments(segments, jd):
    """Geocentric position and velocity from the finest covering segment; NaN outside all segments."""
    jd = np.atleast_1d(np.asarray(jd, dtype=float))
    position = np.full((3, jd.size), np.nan)
    velocity = np.full((3, jd.size), np.nan)
    index = finest_segment_index(segments, jd)
    for i in np.unique(index[index >= 0]):
        mask = index == i
        position[:, mask], velocity[:, mask] = segments[i].evaluate(jd[mask])
    return position, velocity


class GeocentricEphemeris(VectorFunction):
    """
    Skyfield vector from the geocenter to the asteroid, interpolated from Horizons segments.
    Use as `earth + GeocentricEphemeris(segments)`; times outside the segments give NaN
    (switching to the MPC orbit there is the caller's job).
    """
    center = 399
    ephemeris = None

    def __init__(self, segments, target='horizons'):
        self.segments = segments
        self.target = target

    @property
    def target_name(self):
        return str(self.target)

    def _at(self, t):
        jd = np.asarray(t.whole + t.tdb_fraction, dtype=float)
        position, velocity = evaluate_segments(self.segments, jd.ravel())
        if jd.ndim == 0:
            position, velocity = position[:, 0], velocity[:, 0]
        else:
            position = position.reshape((3,) + jd.shape)
            velocity = velocity.reshape((3,) + jd.shape)
        return position, velocity, None, None
