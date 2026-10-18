import math
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.commons import online_trajectory as ot

ARCSEC = math.pi / (180.0 * 3600.0)
DAY = 86400.0


def _unit(ra, dec):
    return ot.radec_to_unit(ra, dec)


def _polyline_error(result, evaluate, fractions=(0.13, 0.43, 0.83)):
    """Max angular distance of independent check points (not the sampler's 1/4, 1/2, 3/4) from the result."""
    t0, t1 = result.times[:-1], result.times[1:]
    a = _unit(result.ra[:-1], result.dec[:-1])
    b = _unit(result.ra[1:], result.dec[1:])
    worst = 0.0
    for f in fractions:
        ra, dec = evaluate(t0 + (t1 - t0) * f)
        worst = max(worst, float(np.max(ot.arc_distance(_unit(ra, dec), a, b))))
    return worst


class CountingEvaluator:
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0
        self.evaluated = 0

    def __call__(self, seconds):
        self.calls += 1
        self.evaluated += len(seconds)
        return self.fn(np.asarray(seconds, dtype=float))


def equator_path(rate_rad_per_day=0.01):
    return lambda t: (t / DAY * rate_rad_per_day, np.zeros_like(t))


def small_circle_path(dec=1.5, rate_rad_per_day=0.4):
    # Constant declination near the pole is a small circle: 6 h steps (~0.4 deg) deviate ~18 arcsec.
    return lambda t: (t / DAY * rate_rad_per_day, np.full_like(t, dec))


def loop_path(t):
    # Retrograde loop: forward motion plus a circle, like a minor planet near opposition.
    days = t / DAY
    phase = 2.0 * math.pi * days / 60.0
    ra = 1.0 + 0.002 * days + 0.05 * np.sin(phase)
    dec = 0.2 + 0.03 * np.cos(phase)
    return ra, dec


def return_path(t):
    # Stationary point: goes east, stops at day 50 and returns along the same track.
    days = t / DAY
    return 2.0 + 0.0004 * (50.0 - np.abs(days - 50.0)) ** 2, np.full_like(t, 0.1)


class GeometryTestCase(unittest.TestCase):
    def test_arc_distance_on_arc_and_beside_it(self):
        a, b = _unit(0.0, 0.0), _unit(0.1, 0.0)
        self.assertAlmostEqual(float(ot.arc_distance(_unit(0.05, 0.0), a, b)), 0.0, places=12)
        self.assertAlmostEqual(float(ot.arc_distance(_unit(0.05, 0.01), a, b)), 0.01, places=9)

    def test_arc_distance_beyond_arc_end_uses_end_point(self):
        a, b = _unit(0.0, 0.0), _unit(0.1, 0.0)
        # On the great circle but outside the arc: distance from the whole circle would be zero.
        self.assertAlmostEqual(float(ot.arc_distance(_unit(0.3, 0.0), a, b)), 0.2, places=9)
        self.assertAlmostEqual(float(ot.arc_distance(_unit(-0.05, 0.0), a, b)), 0.05, places=9)

    def test_arc_distance_degenerate_ends(self):
        a = _unit(1.0, 0.5)
        p = _unit(1.0, 0.6)
        self.assertAlmostEqual(float(ot.arc_distance(p, a, a)), 0.1, places=9)
        antipode = -a
        self.assertTrue(np.isfinite(ot.arc_distance(p, a, antipode)))

    def test_arc_distance_across_ra_zero_and_near_pole(self):
        a, b = _unit(2 * math.pi - 0.01, 0.0), _unit(0.01, 0.0)
        self.assertAlmostEqual(float(ot.arc_distance(_unit(0.0, 0.0), a, b)), 0.0, places=12)
        a, b = _unit(0.0, math.pi / 2 - 0.001), _unit(math.pi, math.pi / 2 - 0.001)
        # The short arc passes over the pole.
        self.assertAlmostEqual(float(ot.arc_distance(_unit(0.0, math.pi / 2), a, b)), 0.0, places=9)


class SamplerTestCase(unittest.TestCase):
    def sample(self, fn, days=30.0, anchors_step_days=1.0, **kwargs):
        evaluator = CountingEvaluator(fn)
        anchors = list(np.arange(0.0, days * DAY + 1.0, anchors_step_days * DAY))
        kwargs.setdefault('max_step_s', 6 * 3600.0)
        result = ot.sample_trajectory(anchors, evaluator, **kwargs)
        return result, evaluator, anchors

    def assert_within_tolerance(self, result, fn):
        self.assertEqual(result.status, 'ok')
        self.assertLessEqual(_polyline_error(result, fn), ot.TOLERANCE_ARCSEC * ARCSEC)

    def test_great_circle_needs_only_base_grid(self):
        result, evaluator, anchors = self.sample(equator_path(0.001))
        self.assertEqual(result.status, 'ok')
        self.assertEqual(len(result.times), 30 * 4 + 1)
        self.assertEqual(result.rounds, 0)
        self.assertEqual(evaluator.calls, 2)

    def test_anchors_start_and_end_are_kept_exactly(self):
        fn = small_circle_path()
        anchors = [0.0, 0.7 * DAY, 3.0 * DAY, 3.5 * DAY]
        result = ot.sample_trajectory(anchors, fn, max_step_s=6 * 3600.0)
        for t in anchors:
            self.assertIn(t, result.times)
        self.assertEqual(result.times[0], 0.0)
        self.assertEqual(result.times[-1], 3.5 * DAY)
        self.assertTrue(np.all(np.diff(result.times) > 0))

    def test_small_circle_is_refined_to_tolerance(self):
        fn = small_circle_path()
        result, _, _ = self.sample(fn, days=10)
        self.assertGreater(result.rounds, 0)
        self.assert_within_tolerance(result, fn)

    def test_segments_are_not_longer_than_limit(self):
        result, _, _ = self.sample(equator_path(0.5), days=5)
        a = _unit(result.ra[:-1], result.dec[:-1])
        b = _unit(result.ra[1:], result.dec[1:])
        self.assertLessEqual(float(np.max(ot.angle_between(a, b))), math.radians(ot.MAX_SEGMENT_DEG) + 1e-12)

    def test_loop_and_return_paths(self):
        for fn in (loop_path, return_path):
            with self.subTest(fn=fn.__name__):
                result, _, _ = self.sample(fn, days=100, anchors_step_days=10)
                self.assert_within_tolerance(result, fn)

    def test_return_inside_one_interval_is_detected(self):
        # Without a time limit the ends of [0, 100] days coincide; the check points must split it.
        result = ot.sample_trajectory([0.0, 100 * DAY], return_path, max_step_s=1000 * DAY)
        self.assertGreater(len(result.times), 2)
        self.assert_within_tolerance(result, return_path)

    def test_ra_wrap_and_pole(self):
        paths = {
            'wrap': lambda t: (np.mod(2 * math.pi - 0.05 + t / DAY * 0.01, 2 * math.pi), np.full_like(t, 0.3)),
            'pole': lambda t: (t / DAY * 0.3, np.full_like(t, math.pi / 2 - 0.01)),
        }
        for name, fn in paths.items():
            with self.subTest(name=name):
                result, _, _ = self.sample(fn, days=10)
                self.assert_within_tolerance(result, fn)

    def test_evaluations_are_batched_per_round(self):
        result, evaluator, _ = self.sample(small_circle_path(), days=30)
        self.assertEqual(evaluator.calls, result.rounds + 2)
        self.assertEqual(evaluator.evaluated, result.evaluations)
        self.assertGreater(len(result.times), evaluator.calls)

    def test_large_batches_are_split(self):
        _, evaluator, _ = self.sample(equator_path(0.001), days=30, max_batch=50)
        self.assertEqual(evaluator.calls, math.ceil(121 / 50) + math.ceil(360 / 50))

    def test_check_times_are_reused(self):
        result, evaluator, _ = self.sample(small_circle_path(), days=10)
        # Every evaluated time is unique: children reuse their parent's check times.
        self.assertEqual(evaluator.evaluated, result.evaluations)
        self.assertLessEqual(len(result.times), result.evaluations)

    def test_limits_return_whole_interval(self):
        cases = {
            ot.LIMIT_MAX_ROUNDS: dict(max_rounds=0),
            ot.LIMIT_MAX_POINTS: dict(max_points=130),
            ot.LIMIT_MAX_EVALUATIONS: dict(max_evaluations=200),
        }
        for reason, limits in cases.items():
            with self.subTest(reason=reason):
                result, evaluator, anchors = self.sample(small_circle_path(), days=30, **limits)
                self.assertEqual(result.status, 'limited')
                self.assertEqual(result.limit_reason, reason)
                for t in anchors:
                    self.assertIn(t, result.times)
                self.assertLessEqual(len(result.times), limits.get('max_points', ot.MAX_POINTS))
                self.assertLessEqual(evaluator.evaluated, limits.get('max_evaluations', ot.MAX_EVALUATIONS))

    def test_non_finite_position_is_an_error(self):
        def fn(t):
            ra, dec = equator_path()(t)
            dec[-1] = np.nan
            return ra, dec
        with self.assertRaises(ot.TrajectoryEvaluationError):
            self.sample(fn, days=2)


class RequestModelTestCase(unittest.TestCase):
    def source(self, **overrides):
        values = dict(
            kind='comet', object_id='C2026A1', label='C/2026 A1', trajectory_id='COMET_TRAJ_C2026A1',
            trajectory_type='comet', elements={'eccentricity': 0.5, 'perihelion_distance_au': 1.0},
            build_body=lambda ts, sun: None, observer=None,
            dt_from=datetime(2026, 1, 1, tzinfo=timezone.utc), dt_to=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        values.update(overrides)
        return ot.TrajectorySource(**values)

    def test_normalize_interval(self):
        dt_from, dt_to = ot.normalize_interval('2026-01-01', '2026-03-01')
        self.assertEqual(dt_from, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(dt_to, datetime(2026, 3, 1, tzinfo=timezone.utc))
        for bad in (('2026-01-02', '2026-01-01'), ('2026-01-01', '2026-01-01'), ('x', '2026-01-01'), (None, '2026-01-01')):
            with self.subTest(bad=bad), self.assertRaises(ot.TrajectoryRequestError):
                ot.normalize_interval(*bad)

    def test_long_interval_is_shortened_everywhere(self):
        dt_from, dt_to = ot.normalize_interval('2026-01-01', '2028-01-01')
        self.assertEqual(dt_to - dt_from, timedelta(days=365))
        source = self.source(dt_from=dt_from, dt_to=dt_to)
        self.assertEqual(ot.interval_args(source), {'traj_from': '2026-01-01', 'traj_to': '2027-01-01'})
        descriptor = ot.build_descriptor(source, '/comet/x/chart/trajectory-v1')
        self.assertEqual(descriptor['traj_to'], '2027-01-01')

    def test_request_key_and_revision(self):
        base = self.source()
        self.assertEqual(base.request_key, self.source().request_key)
        self.assertEqual(base.revision, self.source().revision)
        for change in (dict(object_id='other'), dict(dt_to=datetime(2026, 2, 2, tzinfo=timezone.utc)),
                       dict(observer=(50.0, 14.0, 0.0))):
            with self.subTest(change=change):
                self.assertNotEqual(base.request_key, self.source(**change).request_key)
        self.assertNotEqual(self.source(observer=(50.0, 14.0, 0.0)).request_key,
                            self.source(observer=(50.0, 14.1, 0.0)).request_key)
        for change in (dict(elements={'eccentricity': 0.51, 'perihelion_distance_au': 1.0}), dict(label='Other')):
            with self.subTest(change=change):
                changed = self.source(**change)
                self.assertEqual(base.request_key, changed.request_key)
                self.assertNotEqual(base.revision, changed.revision)
        base_revision = base.revision
        with patch.object(ot, 'ALGORITHM_VERSION', ot.ALGORITHM_VERSION + 1):
            self.assertNotEqual(base_revision, self.source().revision)

    def test_revision_ignores_numpy_types(self):
        numpy_elements = {'eccentricity': np.float64(0.5), 'perihelion_distance_au': np.float64(1.0)}
        self.assertEqual(self.source().revision, self.source(elements=numpy_elements).revision)

    def test_orbit_elements_use_only_orbit_fields(self):
        row = pd.Series({'designation': 'C/2026 A1', 'eccentricity': 0.5, 'mag': 9.0, 'cur_ra': 1.0})
        elements = ot.orbit_elements(row, ot.COMET_ELEMENT_FIELDS)
        self.assertNotIn('mag', elements)
        self.assertEqual(elements['eccentricity'], 0.5)
        self.assertIsNone(elements['perihelion_year'])

    def test_label_times_match_pdf_trajectory(self):
        labels = ot.label_times(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc))
        self.assertEqual([text for _, text in labels][:5], ['01.01.', '06', '11', '16', '21'])
        # Raster of 5 days ends on 25.02., the end of the interval is labeled too.
        self.assertEqual(labels[-2], (datetime(2026, 2, 25, tzinfo=timezone.utc), '25'))
        self.assertEqual(labels[-1], (datetime(2026, 3, 1, tzinfo=timezone.utc), '01.03.'))
        on_raster = ot.label_times(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 8, tzinfo=timezone.utc))
        self.assertEqual([text for _, text in on_raster][-2:], ['07', '08'])

    def test_payload_cache(self):
        ot.clear_trajectory_cache()
        calls = []

        def compute(source):
            calls.append(source)
            return {'request_key': source.request_key}

        source = self.source()
        self.assertIs(ot.get_trajectory_payload(source, compute), ot.get_trajectory_payload(source, compute))
        self.assertEqual(len(calls), 1)
        ot.get_trajectory_payload(self.source(label='Other'), compute)
        self.assertEqual(len(calls), 2)
        ot.clear_trajectory_cache()

    def test_payload_cache_is_bounded(self):
        ot.clear_trajectory_cache()

        def compute(source):
            return {}

        for i in range(ot.CACHE_SIZE + 5):
            ot.get_trajectory_payload(self.source(object_id=str(i)), compute)
        self.assertEqual(len(ot._payload_cache._items), ot.CACHE_SIZE)
        ot.clear_trajectory_cache()


@unittest.skipUnless(os.path.exists('de421.bsp'), 'needs local de421.bsp')
class SkyfieldPayloadTestCase(unittest.TestCase):
    COMET = pd.Series({
        'designation': 'Test comet', 'perihelion_year': 2026, 'perihelion_month': 9, 'perihelion_day': 20.125,
        'perihelion_distance_au': 0.8, 'eccentricity': 0.99, 'inclination_degrees': 45.0,
        'longitude_of_ascending_node_degrees': 120.0, 'argument_of_perihelion_degrees': 70.0,
    })

    def source(self, observer=None):
        from skyfield.data import mpc
        from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
        comet = self.COMET
        dt_from, dt_to = ot.normalize_interval('2026-09-01', '2026-10-15')
        return ot.TrajectorySource(
            kind='comet', object_id='test', label='Test comet', trajectory_id='COMET_TRAJ_test',
            trajectory_type='comet', elements=ot.orbit_elements(comet, ot.COMET_ELEMENT_FIELDS),
            build_body=lambda ts, sun: sun + mpc.comet_orbit(comet, ts, GM_SUN),
            observer=observer, dt_from=dt_from, dt_to=dt_to, with_sun=True,
        )

    def test_payload_matches_labels_and_skyfield_positions(self):
        from skyfield.api import load
        from skyfield.data import mpc
        from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

        source = self.source()
        payload = ot.compute_trajectory_payload(source)
        self.assertEqual(payload['version'], ot.PAYLOAD_VERSION)
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['request_key'], source.request_key)
        points = payload['trajectory']['points']
        labeled = [p for p in points if p['label']]
        expected = ot.label_times(source.dt_from, source.dt_to)
        self.assertEqual([p['label'] for p in labeled], [text for _, text in expected])
        self.assertTrue(all(p['sun_ra'] is not None for p in labeled))
        self.assertTrue(all(p['sun_ra'] is None and p['sun_dec'] is None for p in points if not p['label']))
        self.assertGreater(len(points), len(labeled))

        ts = load.timescale(builtin=True)
        eph = load('de421.bsp')
        body = eph['sun'] + mpc.comet_orbit(self.COMET, ts, GM_SUN)
        dt, _ = expected[3]
        ra, dec, _ = eph['earth'].at(ts.from_datetime(dt)).observe(body).radec()
        self.assertAlmostEqual(labeled[3]['ra'], ra.radians % (2 * math.pi), places=7)
        self.assertAlmostEqual(labeled[3]['dec'], dec.radians, places=7)
        # The end of the interval (off the raster) is labeled and has the Sun for the tail.
        self.assertEqual(points[-1]['label'], '15')
        self.assertIsNotNone(points[-1]['sun_ra'])

    def test_topocentric_payload_differs(self):
        geo = ot.compute_trajectory_payload(self.source())
        topo = ot.compute_trajectory_payload(self.source(observer=(50.08, 14.42, 0.0)))
        self.assertNotEqual(geo['request_key'], topo['request_key'])
        self.assertNotEqual(geo['trajectory']['points'][0]['ra'], topo['trajectory']['points'][0]['ra'])

    def test_ephemeris_range_is_evaluation_error(self):
        source = self.source()
        source = ot.TrajectorySource(**dict(
            source.__dict__,
            dt_from=datetime(2200, 1, 1, tzinfo=timezone.utc),
            dt_to=datetime(2200, 2, 1, tzinfo=timezone.utc),
        ))
        with self.assertRaises(ot.TrajectoryEvaluationError):
            ot.compute_trajectory_payload(source)


if __name__ == '__main__':
    unittest.main()
