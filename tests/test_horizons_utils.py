import hashlib
import math
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
from skyfield.api import load, wgs84

from app import create_app, db
from app.commons import horizons_utils as hu
from app.commons import neo_ephemeris_utils, neo_utils
from app.models import MinorPlanet, NeoEphemerisSegment

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures', 'horizons')
DE421 = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'de421.bsp')

NV_2016 = ('DES=2016 NV;', 2461382.5, 2461384.5, [2461382.7201, 2461383.1337, 2461384.0119])
BU_2023 = ('DES=2023 BU;', 2459971.0, 2459972.0, [2459971.5150, 2459971.5203, 2459971.5212, 2459971.5300])
SITES = {'geocenter': None, 'prague': (50.1, 14.4, 300.0), 'chile': (-30.2, -70.7, 2200.0)}


def _fixture_key(command, start, stop, step):
    return hashlib.sha1('{}|{:.9f}|{:.9f}|{:g}'.format(command, start, stop, step).encode()).hexdigest()[:16]


def replay_fetch(command, start, stop, step):
    """Recorded Horizons responses (tests/fixtures/horizons), keyed like the recording script."""
    with open(os.path.join(FIXTURES, 'vectors_{}.txt'.format(_fixture_key(command, start, stop, step)))) as f:
        return hu.parse_vector_table(f.read())


def _read_observer_fixture(name, site):
    path = os.path.join(FIXTURES, 'observer_{}_{}.txt'.format(name, site))
    if not os.path.exists(path):
        return None
    with open(path) as f:
        body = f.read().split('$$SOE')[1].split('$$EOE')[0]
    rows = [line.split(',') for line in body.strip().splitlines()]
    return np.radians([float(r[3]) for r in rows]), np.radians([float(r[4]) for r in rows])


def _separation_arcsec(ra1, dec1, ra2, dec2):
    cos = np.sin(dec1) * np.sin(dec2) + np.cos(dec1) * np.cos(dec2) * np.cos(ra1 - ra2)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))) * 3600.0


# --- Synthetic hyperbolic flyby around the Earth ------------------------------------------------

GM_EARTH_KM3_S2 = 398600.4418


def synthetic_flyby(perigee_km=50000.0, perigee_speed_kms=15.0, perigee_jd=2461000.5):
    """Two-body hyperbola around the Earth; returns f(jd array) -> states (n, 6) in au and au/day."""
    e = perigee_km * perigee_speed_kms ** 2 / GM_EARTH_KM3_S2 - 1.0
    a = perigee_km / (e - 1.0)  # |a|
    n = math.sqrt(GM_EARTH_KM3_S2 / a ** 3)  # rad/s

    def states(jd):
        t = (np.asarray(jd, dtype=float) - perigee_jd) * 86400.0
        mean = n * t
        hyp = np.arcsinh(mean / e)
        for _ in range(50):
            hyp -= (e * np.sinh(hyp) - hyp - mean) / (e * np.cosh(hyp) - 1.0)
        dhyp = n / (e * np.cosh(hyp) - 1.0)
        x = a * (e - np.cosh(hyp))
        y = a * math.sqrt(e * e - 1.0) * np.sinh(hyp)
        vx = -a * np.sinh(hyp) * dhyp
        vy = a * math.sqrt(e * e - 1.0) * np.cosh(hyp) * dhyp
        zeros = np.zeros_like(x)
        result = np.stack([x, y, zeros, vx * 86400.0, vy * 86400.0, zeros], axis=1)
        result[:, :3] /= hu.AU_KM
        result[:, 3:] /= hu.AU_KM
        return result

    return states


def synthetic_fetch(states_fn, calls=None):
    def fetch(command, start, stop, step):
        step_days = step / hu.MINUTES_PER_DAY
        count = int(math.floor((stop - start) / step_days + 1e-9)) + 1
        jd = start + np.arange(count) * step_days
        if calls is not None:
            calls.append(step)
        return hu.VectorTable(jd_tdb=jd, states=states_fn(jd), orbit_solution='TEST#1')
    return fetch


class RequestAndParseTestCase(unittest.TestCase):
    def test_request_uses_explicit_coordinate_contract(self):
        params = hu.vector_request_params('DES=2016 NV;', 2461382.5, 2461384.5, 60)
        self.assertEqual(params['CENTER'], '500@399')
        self.assertEqual(params['REF_SYSTEM'], 'ICRF')
        self.assertEqual(params['REF_PLANE'], 'FRAME')
        self.assertEqual(params['VEC_CORR'], 'NONE')
        self.assertEqual(params['TIME_TYPE'], 'TDB')
        self.assertEqual(params['OUT_UNITS'], 'AU-D')
        self.assertEqual(params['VEC_TABLE'], '2')
        self.assertEqual(params['START_TIME'], "'JD 2461382.500000000'")
        self.assertEqual(params['STEP_SIZE'], "'60 m'")

    def test_too_long_request_is_refused_before_sending(self):
        with self.assertRaises(ValueError):
            hu.vector_request_params('433;', 2461330.5, 2461530.5, 1)

    def test_commands(self):
        self.assertEqual(hu.horizons_command(int_designation=433), '433;')
        self.assertEqual(hu.horizons_command(designation='2026 UK'), 'DES=2026 UK;')
        with self.assertRaises(ValueError):
            hu.horizons_command()

    def test_parses_recorded_response(self):
        table = replay_fetch(NV_2016[0], NV_2016[1], NV_2016[2], 60)
        self.assertEqual(len(table.jd_tdb), 49)
        self.assertAlmostEqual(table.jd_tdb[0], 2461382.5)
        self.assertEqual(table.states.shape, (49, 6))
        self.assertEqual(table.orbit_solution, 'JPL#75')
        self.assertTrue(0.03 < np.linalg.norm(table.states[0, :3]) < 0.05)  # 2016 NV ~0.04 au

    def test_error_responses_raise(self):
        for text in ['No matches found.', '$$SOE\n$$EOE',
                     '$$SOE\n2461382.5, A.D., 1, 2, x, 4, 5, 6,\n2461382.6, A.D., 1, 2, 3, 4, 5, 6,\n$$EOE']:
            with self.subTest(text=text), self.assertRaises(hu.HorizonsError):
                hu.parse_vector_table(text)

    def test_http_error_raises_horizons_error(self):
        response = MagicMock()
        response.raise_for_status.side_effect = hu.requests.HTTPError('503')
        with patch.object(hu.requests, 'get', return_value=response), self.assertRaises(hu.HorizonsError):
            hu.fetch_vectors('433;', 2461382.5, 2461383.5, 60)


class InterpolationTestCase(unittest.TestCase):
    def test_hermite_is_exact_for_cubic_motion_and_at_nodes(self):
        coefficients = np.array([[0.01, 1e-3, -2e-4, 3e-5], [0.02, -1e-3, 1e-4, 2e-5], [0.0, 5e-4, 0.0, -1e-5]])

        def states(t):
            powers = np.stack([np.ones_like(t), t, t ** 2, t ** 3])
            dpowers = np.stack([np.zeros_like(t), np.ones_like(t), 2 * t, 3 * t ** 2])
            return np.concatenate([coefficients @ powers, coefficients @ dpowers]).T

        nodes = np.arange(0.0, 2.01, 0.25)
        t = np.linspace(0.0, 2.0, 37)
        position, velocity = hu.hermite_interpolate(0.0, 0.25, states(nodes), t)
        np.testing.assert_allclose(position, states(t)[:, :3].T, atol=1e-15)
        np.testing.assert_allclose(velocity, states(t)[:, 3:].T, atol=1e-14)

    def test_finest_covering_segment_wins_and_outside_is_nan(self):
        def constant(value, count):  # constant position, zero velocity
            states = np.zeros((count, 6))
            states[:, :3] = value
            return states

        coarse = hu.EphemerisSegment(start_jd=0.0, step_minutes=60.0, states=constant(1.0, 25))
        fine = hu.EphemerisSegment(start_jd=0.5, step_minutes=15.0, states=constant(2.0, 9))
        jd = np.array([0.1, 0.55, 2.0])
        self.assertEqual(list(hu.finest_segment_index([coarse, fine], jd)), [0, 1, -1])
        position, _ = hu.evaluate_segments([coarse, fine], jd)
        self.assertAlmostEqual(position[0, 0], 1.0)
        self.assertAlmostEqual(position[0, 1], 2.0)
        self.assertTrue(np.isnan(position[:, 2]).all())


class AdaptiveStepTestCase(unittest.TestCase):
    def test_synthetic_flyby_refines_where_hourly_step_fails(self):
        perigee_jd = 2461000.5
        states_fn = synthetic_flyby(perigee_jd=perigee_jd)
        calls = []
        segments = hu.build_verified_ephemeris('TEST;', perigee_jd - 1.0, perigee_jd + 1.0,
                                               fetch=synthetic_fetch(states_fn, calls))

        coarse = segments[0]
        self.assertEqual(coarse.step_minutes, 60.0)
        self.assertGreater(coarse.max_check_error_arcsec, 1.0)  # hourly step is not enough at 50 000 km
        self.assertTrue(coarse.verified)  # every failing check is covered by a verified finer segment
        finer = segments[1:]
        self.assertTrue(finer and all(s.step_minutes < 60.0 for s in finer))
        self.assertTrue(all(s.verified for s in finer if not s.children))
        # Finer segments cover only the surroundings of the perigee.
        self.assertTrue(all(s.start_jd > perigee_jd - 0.5 and s.end_jd < perigee_jd + 0.5 for s in finer))
        # Every refinement level costs two requests (nodes and midpoint checks).
        self.assertEqual(len(calls), 2 * len(segments))

        # Independent dense check against the analytic flyby.
        jd = np.linspace(perigee_jd - 1.0, perigee_jd + 1.0, 20001)
        position, _ = hu.evaluate_segments(segments, jd)
        errors = hu.interpolation_error_arcsec(position, states_fn(jd)[:, :3].T)
        self.assertLess(errors.max(), 1.0)

    def test_distant_object_needs_only_hourly_step(self):
        segments = hu.build_verified_ephemeris('TEST;', 2461000.0, 2461002.0, fetch=synthetic_fetch(
            synthetic_flyby(perigee_km=5e6, perigee_jd=2461001.0)))
        self.assertEqual([(s.step_minutes, s.verified) for s in segments], [(60.0, True)])

    def test_failure_at_finest_step_is_reported_unverified(self):
        segments = hu.build_verified_ephemeris('TEST;', 2461000.0, 2461001.0, fetch=synthetic_fetch(
            synthetic_flyby(perigee_km=8000.0, perigee_speed_kms=12.0, perigee_jd=2461000.5)),
            tolerance_arcsec=1e-9)
        self.assertFalse(segments[0].verified)
        self.assertEqual(segments[-1].step_minutes, 1.0)
        self.assertFalse(segments[-1].verified)

    def test_recorded_2023_bu_flyby_refines_to_one_minute(self):
        command, start, stop, _ = BU_2023
        segments = hu.build_verified_ephemeris(command, start, stop, fetch=replay_fetch)
        self.assertEqual([s.step_minutes for s in segments], [60.0, 15.0, 5.0, 1.0])
        self.assertTrue(all(s.verified for s in segments))
        self.assertGreater(segments[0].max_check_error_arcsec, 3600.0)  # degrees off with an hourly step
        self.assertLess(segments[-1].max_check_error_arcsec, 1.0)


class CoordinateContractTestCase(unittest.TestCase):
    """Interpolated Horizons vectors reproduce Horizons astrometric ICRF RA/Dec of the same solution."""

    @classmethod
    def setUpClass(cls):
        cls.ts = load.timescale(builtin=True)
        cls.earth = load(DE421)['earth']

    def _check(self, name, case, geocentric_limit, topocentric_limit):
        command, start, stop, tlist = case
        body = self.earth + hu.GeocentricEphemeris(hu.build_verified_ephemeris(command, start, stop,
                                                                                fetch=replay_fetch))
        t = self.ts.tt_jd(np.array(tlist))  # times between table nodes
        checked = 0
        for site, coord in SITES.items():
            reference = _read_observer_fixture(name, site)
            if reference is None:
                continue
            observer = self.earth if coord is None else self.earth + wgs84.latlon(coord[0], coord[1],
                                                                                 elevation_m=coord[2])
            ra, dec, _ = observer.at(t).observe(body).radec()
            separation = _separation_arcsec(ra.radians, dec.radians, *reference)
            limit = geocentric_limit if coord is None else topocentric_limit
            self.assertLess(separation.max(), limit, '{} {}'.format(name, site))
            checked += 1
        self.assertGreaterEqual(checked, 2)

    def test_2016_nv(self):
        self._check('2016NV', NV_2016, geocentric_limit=0.05, topocentric_limit=0.05)

    def test_2023_bu_extreme_flyby(self):
        # Topocentric at ~5 000 km: the remaining ~0.25" comes from the Earth orientation model
        # (UT1, polar motion), not from the ephemeris.
        self._check('2023BU', BU_2023, geocentric_limit=0.05, topocentric_limit=1.0)

    def test_scalar_time(self):
        command, start, stop, tlist = NV_2016
        body = self.earth + hu.GeocentricEphemeris(hu.build_verified_ephemeris(command, start, stop,
                                                                                fetch=replay_fetch))
        ra, dec, _ = self.earth.at(self.ts.tt_jd(tlist[0])).observe(body).radec()
        reference = _read_observer_fixture('2016NV', 'geocenter')
        self.assertLess(_separation_arcsec(ra.radians, dec.radians, reference[0][0], reference[1][0]), 0.05)


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        neo_ephemeris_utils._loaded.clear()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _segments(self):
        command, start, stop, _ = BU_2023
        return hu.build_verified_ephemeris(command, start, stop, fetch=replay_fetch)

    def test_round_trip_and_revision(self):
        planet = MinorPlanet(mpc_designation='K23B00U', designation='2023 BU', is_neo=True)
        db.session.add(planet)
        db.session.commit()
        self.assertEqual(neo_ephemeris_utils.load_neo_ephemeris(planet.id), ([], ''))

        segments = self._segments()
        neo_ephemeris_utils.replace_neo_ephemeris(planet.id, segments, datetime(2023, 1, 26))
        db.session.commit()
        loaded, revision = neo_ephemeris_utils.load_neo_ephemeris(planet.id)

        self.assertEqual(len(loaded), 4)
        self.assertTrue(revision)
        jd = np.linspace(2459971.0, 2459972.0, 501)
        np.testing.assert_array_equal(hu.evaluate_segments(loaded, jd)[0], hu.evaluate_segments(segments, jd)[0])
        self.assertEqual({s.verified for s in loaded}, {True})
        self.assertIs(neo_ephemeris_utils.load_neo_ephemeris(planet.id)[0], loaded)  # cached per revision

        # A new download changes the revision and is loaded instead of the cached version.
        neo_ephemeris_utils.replace_neo_ephemeris(planet.id, segments[:1], datetime(2023, 1, 27))
        db.session.commit()
        reloaded, new_revision = neo_ephemeris_utils.load_neo_ephemeris(planet.id)
        self.assertNotEqual(new_revision, revision)
        self.assertEqual(len(reloaded), 1)

    def test_cleanup_deletes_ended_stale_and_orphaned_segments(self):
        now = datetime(2026, 10, 20, 12, 0)
        now_jd = neo_ephemeris_utils.datetime_to_jd(now)

        def segment(start_jd, hours):
            return hu.EphemerisSegment(start_jd=start_jd, step_minutes=60.0, states=np.zeros((hours + 1, 6)))

        kept = MinorPlanet(mpc_designation='KEPT', is_neo=True)
        unused = MinorPlanet(mpc_designation='UNUSED', is_neo=True, neo_imported_at=now - timedelta(days=40))
        db.session.add_all([kept, unused])
        db.session.flush()
        db.session.add_all([
            neo_ephemeris_utils.segment_to_row(kept.id, segment(now_jd - 1, 72), now),  # current
            neo_ephemeris_utils.segment_to_row(kept.id, segment(now_jd - 10, 24), now),  # ended 9 days ago
            neo_ephemeris_utils.segment_to_row(kept.id, segment(now_jd, 72), now - timedelta(days=31)),  # stale
            neo_ephemeris_utils.segment_to_row(unused.id, segment(now_jd, 72), now),  # of a deleted asteroid
        ])
        db.session.commit()

        neo_utils.cleanup_neo_data(now)

        remaining = NeoEphemerisSegment.query.all()
        self.assertEqual([(s.minor_planet_id, round(s.start_jd - now_jd)) for s in remaining], [(kept.id, -1)])
        self.assertEqual([mp.mpc_designation for mp in MinorPlanet.query.all()], ['KEPT'])


if __name__ == '__main__':
    unittest.main()
