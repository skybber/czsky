"""
Smooth trajectories of comets and minor planets for the online (browser) chart.

The browser projects the points itself, so the path is sampled on the celestial sphere,
independent of the chart center, field size or projection. Positions come from batched
Skyfield evaluations: adding a point never costs a scalar ephemeris call.

The PDF chart uses fchart3's own refinement and does not use this module.
"""

import hashlib
import json
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from fchart3.trajectory.trajectory import _format_trajectory_label, _get_trajectory_time_delta

ALGORITHM_VERSION = 2
PAYLOAD_VERSION = 'trajectory-v1'
EPHEMERIS_NAME = 'de421.bsp'

TOLERANCE_ARCSEC = 10.0
# Intervals are split above 80 % of the tolerance, as a reserve for errors between check points.
SPLIT_TOLERANCE_ARCSEC = 8.0
MAX_SEGMENT_DEG = 0.5
MAX_STEP_TOPOCENTRIC = timedelta(hours=6)
MAX_STEP_GEOCENTRIC = timedelta(hours=12)
MAX_INTERVAL_DAYS = 365

MAX_ROUNDS = 14
MAX_POINTS = 4096
MAX_EVALUATIONS = 32768
MAX_BATCH = 4096

COORD_DECIMALS = 8
CACHE_SIZE = 32

ARCSEC_TO_RAD = math.pi / (180.0 * 3600.0)

LIMIT_MAX_ROUNDS = 'max_rounds'
LIMIT_MAX_POINTS = 'max_points'
LIMIT_MAX_EVALUATIONS = 'max_evaluations'


class TrajectoryRequestError(Exception):
    """Invalid request (HTTP 400)."""


class TrajectoryEvaluationError(Exception):
    """Positions can not be computed for the interval (HTTP 422)."""


# --- Geometry -------------------------------------------------------------------------------

def radec_to_unit(ra, dec) -> np.ndarray:
    ra = np.asarray(ra, dtype=float)
    dec = np.asarray(dec, dtype=float)
    cos_dec = np.cos(dec)
    return np.stack((cos_dec * np.cos(ra), cos_dec * np.sin(ra), np.sin(dec)), axis=-1)


def angle_between(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Angle between unit vectors; stable for tiny and near-antipodal angles."""
    return np.arctan2(np.linalg.norm(np.cross(u, v), axis=-1), np.sum(u * v, axis=-1))


def arc_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Angular distance of unit vectors p from the shorter great-circle arc a-b (not the whole circle).

    Points whose foot on the great circle lies outside the arc are measured to the nearer end.
    Equal or antipodal ends have no unique arc and use the end distances only.
    """
    end_dist = np.minimum(angle_between(p, a), angle_between(p, b))
    n = np.cross(a, b)
    n_len = np.linalg.norm(n, axis=-1)
    valid = n_len > 1e-15
    n_hat = n / np.where(valid, n_len, 1.0)[..., None]
    sin_dist = np.sum(p * n_hat, axis=-1)
    foot = p - sin_dist[..., None] * n_hat
    after_a = np.sum(np.cross(a, foot) * n_hat, axis=-1) >= 0.0
    before_b = np.sum(np.cross(foot, b) * n_hat, axis=-1) >= 0.0
    inside = after_a & before_b
    circle_dist = np.arcsin(np.clip(np.abs(sin_dist), 0.0, 1.0))
    return np.where(valid & inside, np.minimum(circle_dist, end_dist), end_dist)


# --- Sampler --------------------------------------------------------------------------------

@dataclass
class SampleResult:
    times: np.ndarray
    ra: np.ndarray
    dec: np.ndarray
    status: str = 'ok'
    limit_reason: Optional[str] = None
    evaluations: int = 0
    rounds: int = 0


def _base_grid(anchor_times: Sequence[float], max_step_s: float) -> List[float]:
    times = []
    for t0, t1 in zip(anchor_times, anchor_times[1:]):
        n = max(1, math.ceil((t1 - t0) / max_step_s - 1e-9))
        times.extend(t0 + (t1 - t0) * k / n for k in range(n))
    times.append(anchor_times[-1])
    return times


def sample_trajectory(
    anchor_times: Sequence[float],
    evaluate: Callable[[np.ndarray], Tuple[np.ndarray, np.ndarray]],
    *,
    max_step_s: float,
    split_tolerance_rad: float = SPLIT_TOLERANCE_ARCSEC * ARCSEC_TO_RAD,
    max_segment_rad: float = math.radians(MAX_SEGMENT_DEG),
    max_rounds: int = MAX_ROUNDS,
    max_points: int = MAX_POINTS,
    max_evaluations: int = MAX_EVALUATIONS,
    max_batch: int = MAX_BATCH,
) -> SampleResult:
    """
    Adaptively sample a path given by evaluate(times) -> (ra, dec) in radians.

    anchor_times are sorted seconds that are always part of the result (labeled points, start, end).
    The base grid adds times so no interval exceeds max_step_s. Each round checks all active
    intervals at 1/4, 1/2 and 3/4 of their time span, evaluating missing times in batches, and
    halves an interval whose check point lies farther than split_tolerance_rad from the arc
    between its ends, or whose ends are farther apart than max_segment_rad. Halving keeps
    the check times of a parent as exact times of its children, so they are evaluated once.

    When a limit is reached, the current subdivision is returned (whole interval, all anchors)
    with status 'limited' and the limit name in limit_reason.
    """
    anchors = sorted(set(float(t) for t in anchor_times))
    if len(anchors) < 2:
        raise TrajectoryRequestError('Trajectory needs at least two times.')

    status, limit_reason = 'ok', None
    base = _base_grid(anchors, max_step_s)
    if len(base) > max_points or len(base) > max_evaluations:
        base = anchors
        status = 'limited'
        limit_reason = LIMIT_MAX_POINTS if len(base) > max_points else LIMIT_MAX_EVALUATIONS

    known: Dict[float, Tuple[float, float]] = {}
    evaluations = 0

    def evaluate_missing(times: List[float]):
        nonlocal evaluations
        for i in range(0, len(times), max_batch):
            block = times[i:i + max_batch]
            ra, dec = evaluate(np.asarray(block, dtype=float))
            ra = np.atleast_1d(np.asarray(ra, dtype=float))
            dec = np.atleast_1d(np.asarray(dec, dtype=float))
            if ra.shape != (len(block),) or dec.shape != (len(block),):
                raise TrajectoryEvaluationError('Unexpected shape of evaluated positions.')
            if not (np.all(np.isfinite(ra)) and np.all(np.isfinite(dec))):
                raise TrajectoryEvaluationError('Position is not finite.')
            evaluations += len(block)
            for t, r, d in zip(block, ra, dec):
                known[t] = (float(r), float(d))

    evaluate_missing(base)

    def unit(times):
        return radec_to_unit([known[t][0] for t in times], [known[t][1] for t in times])

    done: List[Tuple[float, float]] = []
    active = list(zip(base, base[1:]))
    rounds = 0

    while active:
        mids = [(t0 + t1) / 2.0 for t0, t1 in active]
        checks = [((t0 + m) / 2.0, m, (m + t1) / 2.0) for (t0, t1), m in zip(active, mids)]
        missing = sorted({t for chk in checks for t in chk if t not in known})
        if evaluations + len(missing) > max_evaluations:
            status, limit_reason = 'limited', LIMIT_MAX_EVALUATIONS
            break
        evaluate_missing(missing)

        a = unit([t0 for t0, _ in active])
        b = unit([t1 for _, t1 in active])
        p = np.stack([unit(chk) for chk in zip(*checks)], axis=1)
        error = np.max(arc_distance(p, a[:, None, :], b[:, None, :]), axis=1)
        span = np.array([t1 - t0 for t0, t1 in active])
        too_far = error > split_tolerance_rad
        too_long = angle_between(a, b) > max_segment_rad
        too_slow = span > max_step_s * (1 + 1e-9)
        split = too_far | too_long | too_slow

        n_split = int(np.count_nonzero(split))
        if n_split == 0:
            done.extend(active)
            active = []
            break
        if rounds >= max_rounds:
            status, limit_reason = 'limited', LIMIT_MAX_ROUNDS
            break
        if len(done) + len(active) + 1 + n_split > max_points:
            status, limit_reason = 'limited', LIMIT_MAX_POINTS
            break

        next_active = []
        for (t0, t1), m, s in zip(active, mids, split):
            if s:
                next_active.append((t0, m))
                next_active.append((m, t1))
            else:
                done.append((t0, t1))
        active = next_active
        rounds += 1

    done.extend(active)
    times = sorted({t for interval in done for t in interval})
    return SampleResult(
        times=np.asarray(times, dtype=float),
        ra=np.asarray([known[t][0] for t in times], dtype=float),
        dec=np.asarray([known[t][1] for t in times], dtype=float),
        status=status,
        limit_reason=limit_reason,
        evaluations=evaluations,
        rounds=rounds,
    )


# --- Request model --------------------------------------------------------------------------

def _parse_iso_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or '').strip())
    except ValueError:
        raise TrajectoryRequestError('Invalid date: {!r}'.format(value))


def normalize_interval(traj_from, traj_to) -> Tuple[datetime, datetime]:
    """Dates mean midnight UTC; a range over MAX_INTERVAL_DAYS is shortened from its start."""
    d1 = _parse_iso_date(traj_from)
    d2 = _parse_iso_date(traj_to)
    if d1 >= d2:
        raise TrajectoryRequestError('Trajectory start must be before its end.')
    dt_from = datetime(d1.year, d1.month, d1.day, tzinfo=timezone.utc)
    dt_to = datetime(d2.year, d2.month, d2.day, tzinfo=timezone.utc)
    if (dt_to - dt_from).days > MAX_INTERVAL_DAYS:
        dt_to = dt_from + timedelta(days=MAX_INTERVAL_DAYS)
    return dt_from, dt_to


def _canonical(value):
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return repr(f) if math.isfinite(f) else str(f)
    return str(value).strip()


def _fingerprint(data) -> str:
    text = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]


@dataclass(frozen=True)
class TrajectorySource:
    """
    One trajectory request: object, its orbit, observer and the effective interval.

    build_body(ts, sun) returns the Skyfield body; elements are the orbit values it uses
    (including the revision of any other position source, e.g. a Horizons ephemeris).
    observer is (lat_deg, lon_deg, elevation_m) for a topocentric path or None for geocentric.
    breaks are UTC instants where the body switches its position source and may jump;
    the path is sampled separately on each side and interrupted there.
    """
    kind: str
    object_id: str
    label: str
    trajectory_id: str
    trajectory_type: str
    elements: Mapping[str, object]
    build_body: Callable = field(compare=False, hash=False, repr=False)
    observer: Optional[Tuple[float, float, float]]
    dt_from: datetime
    dt_to: datetime
    with_sun: bool = False
    breaks: Tuple[datetime, ...] = ()

    def _observer_key(self):
        if self.observer is None:
            return ['geocentric']
        lat, lon, elevation = self.observer
        return ['topocentric', round(float(lat), 6), round(float(lon), 6),
                round(float(elevation), 1)]

    @property
    def request_key(self) -> str:
        return _fingerprint({
            'kind': self.kind,
            'id': self.object_id,
            'from': self.dt_from.isoformat(),
            'to': self.dt_to.isoformat(),
            'observer': self._observer_key(),
        })

    @property
    def revision(self) -> str:
        return _fingerprint({
            'elements': {k: _canonical(v) for k, v in self.elements.items()},
            'ephemeris': EPHEMERIS_NAME,
            'algorithm': ALGORITHM_VERSION,
            'tolerance': TOLERANCE_ARCSEC,
            'label': self.label,
            'trajectory_id': self.trajectory_id,
            'with_sun': self.with_sun,
            'breaks': [b.isoformat() for b in self.breaks],
        })

    @property
    def max_step(self) -> timedelta:
        return MAX_STEP_TOPOCENTRIC if self.observer is not None else MAX_STEP_GEOCENTRIC


def interval_args(source: TrajectorySource) -> Dict[str, str]:
    return {
        'traj_from': source.dt_from.date().isoformat(),
        'traj_to': source.dt_to.date().isoformat(),
    }


def build_descriptor(source: TrajectorySource, url: str) -> Dict[str, object]:
    """Small scene descriptor; computes no positions."""
    descriptor = {
        'url': url,
        'request_key': source.request_key,
        'revision': source.revision,
    }
    descriptor.update(interval_args(source))
    return descriptor


def label_times(dt_from: datetime, dt_to: datetime) -> List[Tuple[datetime, str]]:
    """
    Labeled times and texts on the raster of the PDF trajectory (fchart3.build_trajectory).

    The end of the interval is labeled too, also when it is off the raster.
    """
    step, _ = _get_trajectory_time_delta(dt_from, dt_to)
    labels = []
    cur, prev = dt_from, None
    while cur <= dt_to:
        labels.append((cur, _format_trajectory_label(cur, prev)))
        prev = cur
        cur += step
    if prev < dt_to:
        labels.append((dt_to, _format_trajectory_label(dt_to, prev)))
    return labels


# --- Skyfield evaluation and payload --------------------------------------------------------

def _skyfield_context():
    from skyfield.api import load
    ts = load.timescale(builtin=True)
    eph = load(EPHEMERIS_NAME)
    return ts, eph['sun'], eph['earth']


def _times_from_offsets(ts, dt_from: datetime, seconds: np.ndarray):
    return ts.utc(dt_from.year, dt_from.month, dt_from.day, dt_from.hour, dt_from.minute,
                  dt_from.second + np.asarray(seconds, dtype=float))


BREAK_MARGIN_S = 1.0


def _join_sample_results(results: Sequence[SampleResult]) -> SampleResult:
    """Concatenates parts with a NaN gap entry between them; the first non-ok status wins."""
    gap = np.array([np.nan])
    times, ra, dec = [], [], []
    for i, part in enumerate(results):
        if i:
            times.append(gap), ra.append(gap), dec.append(gap)
        times.append(np.asarray(part.times, dtype=float))
        ra.append(np.asarray(part.ra, dtype=float))
        dec.append(np.asarray(part.dec, dtype=float))
    failed = next((part for part in results if part.status != 'ok'), None)
    return SampleResult(times=np.concatenate(times), ra=np.concatenate(ra), dec=np.concatenate(dec),
                        status=failed.status if failed else 'ok',
                        limit_reason=failed.limit_reason if failed else None,
                        evaluations=sum(p.evaluations for p in results), rounds=max(p.rounds for p in results))


def compute_trajectory_payload(source: TrajectorySource) -> Dict[str, object]:
    from skyfield.api import wgs84
    from skyfield.errors import EphemerisRangeError

    ts, sun, earth = _skyfield_context()
    observer = earth
    if source.observer is not None:
        lat, lon, elevation = source.observer
        observer = earth + wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon,
                                        elevation_m=elevation)
    body = source.build_body(ts, sun)

    def evaluate(seconds):
        t = _times_from_offsets(ts, source.dt_from, seconds)
        ra, dec, _ = observer.at(t).observe(body).radec()
        return ra.radians, dec.radians

    labels = label_times(source.dt_from, source.dt_to)
    label_offsets = {(dt - source.dt_from).total_seconds(): text for dt, text in labels}
    end_offset = (source.dt_to - source.dt_from).total_seconds()
    anchors = sorted(set(label_offsets) | {0.0, end_offset})

    # Parts between breaks, kept BREAK_MARGIN_S off the break so each side uses one source.
    break_offsets = sorted({o for o in ((b - source.dt_from).total_seconds() for b in source.breaks)
                            if 0.0 < o < end_offset})
    bounds = [0.0] + break_offsets + [end_offset]
    parts = []
    for i, (part_from, part_to) in enumerate(zip(bounds, bounds[1:])):
        if i > 0:
            part_from += BREAK_MARGIN_S
        if i < len(bounds) - 2:
            part_to -= BREAK_MARGIN_S
        if part_to > part_from:
            parts.append(sorted({part_from, part_to} | {o for o in anchors if part_from < o < part_to}))

    try:
        results = [sample_trajectory(part, evaluate, max_step_s=source.max_step.total_seconds()) for part in parts]
        result = results[0] if len(results) == 1 else _join_sample_results(results)
        sun_pos = {}
        if source.with_sun:
            offsets = sorted(label_offsets)
            sun_t = _times_from_offsets(ts, source.dt_from, offsets)
            sun_ra, sun_dec, _ = earth.at(sun_t).observe(sun).radec()
            sun_ra, sun_dec = np.atleast_1d(sun_ra.radians), np.atleast_1d(sun_dec.radians)
            sun_pos = dict(zip(offsets, zip(sun_ra, sun_dec)))
    except EphemerisRangeError as e:
        raise TrajectoryEvaluationError(str(e))

    points = []
    for t, ra, dec in zip(result.times, result.ra, result.dec):
        if not np.isfinite(t):
            # Gap between parts: the renderer interrupts the line at a point without coordinates.
            points.append({'ra': None, 'dec': None, 'label': '', 'sun_ra': None, 'sun_dec': None})
            continue
        label = label_offsets.get(float(t))
        sun_ra = sun_dec = None
        if label is not None and float(t) in sun_pos:
            sun_ra, sun_dec = (round(float(v), COORD_DECIMALS) for v in sun_pos[float(t)])
        points.append({
            'ra': round(float(ra) % (2.0 * math.pi), COORD_DECIMALS),
            'dec': round(float(dec), COORD_DECIMALS),
            'label': label or '',
            'sun_ra': sun_ra,
            'sun_dec': sun_dec,
        })

    payload = {
        'version': PAYLOAD_VERSION,
        'request_key': source.request_key,
        'revision': source.revision,
        'tolerance_arcsec': TOLERANCE_ARCSEC,
        'status': result.status,
        'trajectory': {
            'id': source.trajectory_id,
            'label': source.label,
            'type': source.trajectory_type,
            'points': points,
        },
    }
    if result.limit_reason:
        payload['limit_reason'] = result.limit_reason
    payload.update(interval_args(source))
    return payload


class _LruCache:
    def __init__(self, size: int):
        self.size = size
        self._items: 'OrderedDict[Tuple[str, str], Dict[str, object]]' = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear(self):
        with self._lock:
            self._items.clear()


_payload_cache = _LruCache(CACHE_SIZE)


def get_trajectory_payload(source: TrajectorySource,
                           compute=compute_trajectory_payload) -> Dict[str, object]:
    """Cached payload; a concurrent cold request (thread or worker) may compute it again."""
    key = (source.request_key, source.revision)
    payload = _payload_cache.get(key)
    if payload is None:
        payload = compute(source)
        _payload_cache.put(key, payload)
    return payload


def clear_trajectory_cache():
    _payload_cache.clear()


# --- Orbit elements -------------------------------------------------------------------------

MINOR_PLANET_ELEMENT_FIELDS = (
    'designation', 'epoch_packed', 'semimajor_axis_au', 'eccentricity', 'inclination_degrees',
    'longitude_of_ascending_node_degrees', 'argument_of_perihelion_degrees', 'mean_anomaly_degrees',
)

COMET_ELEMENT_FIELDS = (
    'designation', 'perihelion_year', 'perihelion_month', 'perihelion_day',
    'perihelion_distance_au',
    'eccentricity', 'argument_of_perihelion_degrees', 'longitude_of_ascending_node_degrees',
    'inclination_degrees',
)


def orbit_elements(row, fields: Sequence[str]) -> Dict[str, object]:
    """Orbit values of a Skyfield MPC row used by the orbit model (no magnitudes, positions)."""
    return {name: (row[name] if name in row else None) for name in fields}


# --- HTTP responses -------------------------------------------------------------------------

def _no_shared_cache(response):
    # The observer comes from the session, so the response must not be shared between users.
    response.headers['Cache-Control'] = 'private, no-cache'
    return response


def trajectory_json_response(payload):
    from flask import jsonify
    return _no_shared_cache(jsonify(payload))


def trajectory_error_response(status_code: int, message: str):
    from flask import jsonify
    response = jsonify({'version': PAYLOAD_VERSION, 'error': message})
    response.status_code = status_code
    return _no_shared_cache(response)
