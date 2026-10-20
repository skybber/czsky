"""Phase B: the Horizons ephemeris used by all position computations (docs/plans/neo-horizons-ephemeris.md)."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
from skyfield.api import load
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from app import create_app, db
from app.commons import horizons_utils as hu
from app.commons import minor_planet_utils, neo_ephemeris_utils, neo_utils
from app.commons.online_trajectory import TrajectorySource, compute_trajectory_payload
from app.models import MinorPlanet, NeoCloseApproach, NeoEphemerisSegment

from test_horizons_utils import DE421, NV_2016, _read_observer_fixture, _separation_arcsec, replay_fetch

NV_2016_LINE = ('K16N00V 19.82  0.15 K2669 254.39356  145.15242  255.14563   16.29229  0.2366180  0.69201427'
                '   1.2658804  0 E2026-U38   340   4 2016-2026 0.78 M-v 3Ek MPCLINUX   8803          2016 NV'
                '            20261018\n')
CERES_LINE = ('00001    3.33  0.15 K243V 102.95073   73.36090   80.25353   10.58759  0.0790274  0.21412733'
              '   2.7670775  0 E2024-MB4  7314 125 1801-2024 0.80 M-v 30k MPCLINUX   4000      (1) Ceres'
              '              20240628\n')


def _nv_segments():
    command, start, stop, _ = NV_2016
    return hu.build_verified_ephemeris(command, start, stop, fetch=replay_fetch)


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        neo_ephemeris_utils._loaded.clear()
        self.tmp_dir = tempfile.TemporaryDirectory()
        excerpt = os.path.join(self.tmp_dir.name, 'MPCORB.9999.DAT')
        nea = os.path.join(self.tmp_dir.name, 'NEA.txt')
        with open(excerpt, 'w', encoding='ascii') as f:
            f.write(CERES_LINE)
        with open(nea, 'w', encoding='ascii') as f:
            f.write(NV_2016_LINE)
        self.patches = [patch.object(minor_planet_utils, 'MPCORB_EXCERPT_FILE', excerpt),
                        patch.object(minor_planet_utils, 'NEA_FILE', nea)]
        for p in self.patches:
            p.start()
        minor_planet_utils.reset_minor_planets_cache()
        self.ts = load.timescale(builtin=True)
        self.eph = load(DE421)
        self.sun, self.earth = self.eph['sun'], self.eph['earth']

    def tearDown(self):
        for p in self.patches:
            p.stop()
        minor_planet_utils.reset_minor_planets_cache()
        self.tmp_dir.cleanup()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _nv_with_ephemeris(self):
        nv = MinorPlanet(mpc_designation='K16N00V', designation='2016 NV', is_neo=True,
                         magnitude_H=19.82, magnitude_G=0.15)
        db.session.add(nv)
        db.session.flush()
        neo_ephemeris_utils.replace_neo_ephemeris(nv.id, _nv_segments(), datetime(2026, 12, 1))
        db.session.commit()
        return nv


class HybridBodyTestCase(AppTestCase):
    def test_switches_per_time_between_horizons_and_mpc(self):
        segments = _nv_segments()
        orbit = mpc.mpcorb_orbit(minor_planet_utils.find_mpc_minor_planet('K16N00V'), self.ts, GM_SUN)
        hybrid = hu.HybridMinorPlanetBody(self.earth, self.sun, orbit, segments)
        horizons = self.earth + hu.GeocentricEphemeris(segments)
        mpc_body = self.sun + orbit

        # Mixed array: before, inside and after the coverage (2461382.5 - 2461384.5 TDB).
        t = self.ts.tdb_jd(np.array([2461380.0, 2461383.0, 2461383.7, 2461386.0]))
        position = hybrid.at(t).position.au
        np.testing.assert_allclose(position[:, 1:3], horizons.at(t).position.au[:, 1:3], atol=1e-15)
        np.testing.assert_allclose(position[:, [0, 3]], mpc_body.at(t).position.au[:, [0, 3]], atol=1e-15)
        self.assertEqual(list(hybrid.precise_mask(t)), [False, True, True, False])
        self.assertEqual(list(hybrid.verified_mask(t)), [False, True, True, False])

        # Scalar time and observe() (light time) work like any Skyfield body.
        single = self.ts.tdb_jd(2461383.0)
        ra_h, dec_h, _ = self.earth.at(single).observe(hybrid).radec()
        ra_e, dec_e, _ = self.earth.at(single).observe(horizons).radec()
        self.assertLess(_separation_arcsec(ra_h.radians, dec_h.radians, ra_e.radians, dec_e.radians), 1e-6)

        # The MPC two-body orbit is minutes of arc off near this approach; that is what is fixed.
        ra_m, dec_m, _ = self.earth.at(single).observe(mpc_body).radec()
        self.assertGreater(_separation_arcsec(ra_h.radians, dec_h.radians, ra_m.radians, dec_m.radians), 60.0)

    def test_body_provider(self):
        ceres = MinorPlanet(int_designation=1, mpc_designation='00001', designation='(1) Ceres')
        neo_without = MinorPlanet(mpc_designation='K16N00V', designation='2016 NV', is_neo=True)
        db.session.add_all([ceres, neo_without])
        db.session.commit()
        self.assertNotIsInstance(minor_planet_utils.get_minor_planet_body(ceres, self.ts, self.sun, self.earth),
                                 hu.HybridMinorPlanetBody)
        self.assertNotIsInstance(minor_planet_utils.get_minor_planet_body(neo_without, self.ts, self.sun, self.earth),
                                 hu.HybridMinorPlanetBody)

        neo_ephemeris_utils.replace_neo_ephemeris(neo_without.id, _nv_segments(), datetime(2026, 12, 1))
        db.session.commit()
        self.assertIsInstance(minor_planet_utils.get_minor_planet_body(neo_without, self.ts, self.sun, self.earth),
                              hu.HybridMinorPlanetBody)


class AppPositionsTestCase(AppTestCase):
    def test_app_position_matches_horizons_astrometric(self):
        """Stored ephemeris -> DB load -> body -> get_minor_planet_radec, against Horizons RA/Dec."""
        nv = self._nv_with_ephemeris()
        tlist = NV_2016[3]
        reference_ra, reference_dec = _read_observer_fixture('2016NV', 'geocenter')
        for i, jd_tt in enumerate(tlist):
            dt = self.ts.tt_jd(jd_tt).utc_datetime()
            ra, dec = minor_planet_utils.get_minor_planet_radec(nv, dt)
            self.assertLess(_separation_arcsec(ra, dec, reference_ra[i], reference_dec[i]), 0.05)

    def test_topocentric_position_matches_horizons(self):
        nv = self._nv_with_ephemeris()
        reference_ra, reference_dec = _read_observer_fixture('2016NV', 'prague')
        dt = self.ts.tt_jd(NV_2016[3][1]).utc_datetime()
        ra, dec = minor_planet_utils.get_minor_planet_radec(nv, dt, observer_lat=50.1, observer_lon=14.4,
                                                             observer_elevation=300.0)
        self.assertLess(_separation_arcsec(ra, dec, reference_ra[1], reference_dec[1]), 0.05)

    def test_brightness_and_current_values_use_horizons(self):
        nv = self._nv_with_ephemeris()
        t = self.ts.tdb_jd(2461383.0)
        minor_planet_utils._calculate_minor_planet_brightness(
            nv, minor_planet_utils.find_mpc_minor_planet(nv), self.ts, self.sun, self.earth, t)
        body = self.earth + hu.GeocentricEphemeris(_nv_segments())
        r, delta, earth_sun = minor_planet_utils.sun_earth_body_distances(body, t, self.sun, self.earth)
        expected = minor_planet_utils._get_apparent_magnitude_hg(19.82, 0.15, float(delta), float(r), float(earth_sun))
        self.assertAlmostEqual(nv.eval_mag, expected, places=6)


class LightTimeAtBoundaryTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.segments = _nv_segments()
        orbit = mpc.mpcorb_orbit(minor_planet_utils.find_mpc_minor_planet('K16N00V'), self.ts, GM_SUN)
        self.hybrid = hu.HybridMinorPlanetBody(self.earth, self.sun, orbit, self.segments)
        self.mpc_body = self.sun + orbit
        self.horizons = self.earth + hu.GeocentricEphemeris(self.segments, extrapolate=True)
        self.end = self.segments[0].end_jd
        self.receive_start, self.receive_end = hu.segments_receive_boundaries(self.segments)

    def _radec(self, body, jd):
        ra, dec, _ = self.earth.at(self.ts.tdb_jd(jd)).observe(body).radec()
        return ra.radians, dec.radians

    def test_observe_converges_at_the_boundary(self):
        # Review repro: end + 18.65 s used to raise 'light-travel time failed to converge'.
        for seconds in (0.0, 18.0, 18.4, 18.65, 19.0, 60.0):
            self._radec(self.hybrid, self.end + seconds / 86400.0)
        jd = self.end + np.linspace(-120, 120, 241) / 86400.0
        ra, _ = self._radec(self.hybrid, jd)  # one vector call across the boundary
        self.assertTrue(np.isfinite(ra).all())

    def test_source_switches_at_receive_time_boundary(self):
        # The light time of 2016 NV here is ~18.5 s; the boundary is shifted by it.
        self.assertAlmostEqual((self.receive_end - self.end) * 86400.0, 18.5, delta=0.5)
        for jd, expected in [(self.receive_end - 0.5 / 86400.0, self.horizons),
                             (self.receive_end + 0.5 / 86400.0, self.mpc_body),
                             (self.receive_start - 0.5 / 86400.0, self.mpc_body),
                             (self.receive_start + 0.5 / 86400.0, self.horizons)]:
            ra, dec = self._radec(self.hybrid, jd)
            ra_e, dec_e = self._radec(expected, jd)
            self.assertLess(float(_separation_arcsec(ra, dec, ra_e, dec_e)), 1e-6)


class TrajectoryTestCase(AppTestCase):
    def _source(self, minor_planet, dt_from, dt_to):
        from app.main.solarsystem.minor_planet_views import _minor_planet_trajectory_source
        with self.app.test_request_context('/'), \
                patch('app.main.solarsystem.minor_planet_views.resolve_chart_city_lat_lon',
                      return_value=('X', 50.1, 14.4)):
            return _minor_planet_trajectory_source(minor_planet, dt_from.date().isoformat(), dt_to.date().isoformat())

    def test_path_is_interrupted_at_coverage_boundary(self):
        nv = self._nv_with_ephemeris()
        source = self._source(nv, datetime(2026, 12, 7), datetime(2026, 12, 12))
        self.assertEqual(len(source.breaks), 2)

        payload = compute_trajectory_payload(source)
        points = payload['trajectory']['points']
        gaps = [i for i, p in enumerate(points) if p['ra'] is None]
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all(0 < i < len(points) - 1 for i in gaps))

        # The points next to each gap come from the source of their side (MPC / Horizons / MPC).
        segments = _nv_segments()
        orbit = mpc.mpcorb_orbit(minor_planet_utils.find_mpc_minor_planet('K16N00V'), self.ts, GM_SUN)
        from skyfield.api import wgs84
        observer = self.earth + wgs84.latlon(50.1, 14.4, elevation_m=0.0)
        horizons = self.earth + hu.GeocentricEphemeris(segments, extrapolate=True)
        mpc_body = self.sun + orbit
        margin = timedelta(seconds=1)
        start_break, end_break = source.breaks
        for point, when, body in [(points[gaps[0] - 1], start_break - margin, mpc_body),
                                  (points[gaps[0] + 1], start_break + margin, horizons),
                                  (points[gaps[1] - 1], end_break - margin, horizons),
                                  (points[gaps[1] + 1], end_break + margin, mpc_body)]:
            ra, dec, _ = observer.at(self.ts.from_datetime(when)).observe(body).radec()
            self.assertLess(float(_separation_arcsec(point['ra'], point['dec'], ra.radians, dec.radians)), 0.5)

    def test_new_ephemeris_changes_trajectory_revision(self):
        nv = self._nv_with_ephemeris()
        revision = self._source(nv, datetime(2026, 12, 7), datetime(2026, 12, 12)).revision
        neo_ephemeris_utils.replace_neo_ephemeris(nv.id, _nv_segments()[:1], datetime(2026, 12, 2))
        NeoEphemerisSegment.query.filter_by(minor_planet_id=nv.id).update({'revision': 'changed'})
        db.session.commit()
        self.assertNotEqual(self._source(nv, datetime(2026, 12, 7), datetime(2026, 12, 12)).revision, revision)

    def test_pdf_path_is_clipped_to_coverage(self):
        from app.main.solarsystem.minor_planet_views import _clip_to_horizons_coverage
        coverage = (datetime(2026, 12, 8, tzinfo=timezone.utc), datetime(2026, 12, 10, tzinfo=timezone.utc))
        self.assertEqual(_clip_to_horizons_coverage(datetime(2026, 12, 7), datetime(2026, 12, 12), coverage),
                         (datetime(2026, 12, 8), datetime(2026, 12, 10)))
        self.assertEqual(_clip_to_horizons_coverage(datetime(2026, 12, 1), datetime(2026, 12, 5), coverage),
                         (datetime(2026, 12, 1), datetime(2026, 12, 5)))
        self.assertEqual(_clip_to_horizons_coverage(datetime(2026, 12, 1), datetime(2026, 12, 5), None),
                         (datetime(2026, 12, 1), datetime(2026, 12, 5)))


class DailyJobOrderTestCase(AppTestCase):
    def _approach(self, designation='2016 NV', days=0.0):
        return {'designation': designation, 'approach_time': datetime(2026, 12, 8, 18, 41) + timedelta(days=days),
                'dist_au': 0.037, 'dist_min_au': 0.037, 'dist_max_au': 0.037, 'v_rel_kms': 8.0, 'h': 19.8,
                't_sigma': '<00:01', 'orbit_id': '75'}

    def test_horizons_before_final_filter_and_stored_with_the_asteroid(self):
        calls = []

        def fetch(mpc_row, approach_times, now):
            calls.append((mpc_row['designation'], approach_times, now))
            return _nv_segments()

        # MPC peak 18.2 (within the 0.3 mag margin), Horizons peak 17.9: kept only thanks to Horizons.
        def peak(mpc_row, approach_time, ts, eph, segments=None):
            return (17.9 if segments else 18.2), approach_time

        window_start = datetime(2026, 12, 1)
        with patch.object(neo_utils, 'compute_peak_brightness', side_effect=peak):
            neo_utils.store_close_approaches([self._approach()], window_start, fetch_ephemeris=fetch)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], [datetime(2026, 12, 8, 18, 41)])
        approach = NeoCloseApproach.query.one()
        self.assertEqual(approach.peak_mag, 17.9)
        segments, revision = neo_ephemeris_utils.load_neo_ephemeris(approach.minor_planet_id)
        self.assertTrue(revision)
        self.assertEqual(len(segments), 1)

    def test_distant_approach_far_from_limit_gets_no_horizons_request(self):
        fetch = unittest.mock.MagicMock()
        with patch.object(neo_utils, 'compute_peak_brightness', return_value=(19.0, datetime(2026, 12, 8))):
            neo_utils.store_close_approaches([self._approach() | {'dist_au': 0.1}], datetime(2026, 12, 1),
                                             fetch_ephemeris=fetch)
        fetch.assert_not_called()
        self.assertEqual(NeoCloseApproach.query.count(), 0)

    def test_close_approach_is_decided_by_horizons_even_if_mpc_is_faint(self):
        # Like 2023 BU: the MPC orbit gives a much fainter peak than Horizons.
        def peak(mpc_row, approach_time, ts, eph, segments=None):
            return (11.6 if segments else 19.5), approach_time

        fetch = unittest.mock.MagicMock(return_value=_nv_segments())
        with patch.object(neo_utils, 'compute_peak_brightness', side_effect=peak):
            neo_utils.store_close_approaches([self._approach()], datetime(2026, 12, 1), fetch_ephemeris=fetch)
        fetch.assert_called_once()
        self.assertEqual(NeoCloseApproach.query.one().peak_mag, 11.6)

    def test_horizons_failure_keeps_stored_ephemeris(self):
        nv = self._nv_with_ephemeris()
        revision = neo_ephemeris_utils.neo_ephemeris_revision(nv.id)
        seen_segments = []

        def peak(mpc_row, approach_time, ts, eph, segments=None):
            seen_segments.append(bool(segments))
            return 17.0, approach_time

        with patch.object(neo_utils, 'compute_peak_brightness', side_effect=peak):
            neo_utils.store_close_approaches([self._approach()], datetime(2026, 12, 1),
                                             fetch_ephemeris=unittest.mock.MagicMock(side_effect=hu.HorizonsError('x')))

        self.assertEqual(neo_ephemeris_utils.neo_ephemeris_revision(nv.id), revision)
        self.assertEqual(seen_segments, [True, True])  # preselection and final peak use the stored ephemeris
        self.assertEqual(NeoCloseApproach.query.one().minor_planet_id, nv.id)

    def test_fetch_window_covers_now_and_peak_search(self):
        calls = []
        with patch.object(neo_utils, 'build_verified_ephemeris',
                          side_effect=lambda command, start, stop: calls.append((command, start, stop)) or []):
            now = datetime(2026, 12, 1)
            neo_utils.fetch_neo_ephemeris(minor_planet_utils.find_mpc_minor_planet('K16N00V'),
                                          [datetime(2027, 2, 20)], now)
        command, start, stop = calls[0]
        self.assertEqual(command, 'DES=2016 NV;')
        self.assertAlmostEqual(start, neo_ephemeris_utils.datetime_to_jd(now - timedelta(days=2)))
        self.assertAlmostEqual(stop, neo_ephemeris_utils.datetime_to_jd(datetime(2027, 2, 20) + timedelta(days=31)))


class LightCurveTestCase(AppTestCase):
    def test_light_curve_uses_horizons_inside_coverage(self):
        from app.commons.light_curve_utils import hg_magnitude, minor_planet_light_curve
        nv = self._nv_with_ephemeris()
        dates = [datetime(2026, 12, 9, tzinfo=timezone.utc)]
        mpc_row = minor_planet_utils.find_mpc_minor_planet(nv)
        with_horizons = minor_planet_light_curve(mpc_row, 19.82, 0.15, dates, minor_planet=nv)
        t = self.ts.from_datetimes(dates)
        body = self.earth + hu.GeocentricEphemeris(_nv_segments())
        r, delta, earth_sun = minor_planet_utils.sun_earth_body_distances(body, t, self.sun, self.earth)
        phase = np.degrees(np.arccos((r ** 2 + delta ** 2 - earth_sun ** 2) / (2 * r * delta)))
        np.testing.assert_allclose(with_horizons, hg_magnitude(19.82, 0.15, r, delta, phase), atol=1e-9)


if __name__ == '__main__':
    unittest.main()
