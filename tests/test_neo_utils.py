import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
import unittest.mock
from unittest.mock import patch

from app import create_app, db
from app.commons import minor_planet_utils, neo_utils
from app.commons.neo_utils import (
    CloseApproachSourceError,
    build_designation_index,
    estimate_peak_mag,
    parse_close_approaches,
    store_close_approaches,
    update_neos,
)
from app.models import MinorPlanet, NeoCloseApproach
from imports.import_minor_planets import parse_mpc_hex_flags

CERES_LINE = ('00001    3.33  0.15 K243V 102.95073   73.36090   80.25353   10.58759  0.0790274  0.21412733'
              '   2.7670775  0 E2024-MB4  7314 125 1801-2024 0.80 M-v 30k MPCLINUX   4000      (1) Ceres'
              '              20240628\n')
EROS_LINE = ('00433   10.39  0.15 K2669  62.51145  178.91814  304.26797   10.82855  0.2228780  0.55970463'
             '   1.4582437  0 E2026-TG8 18065  59 1893-2026 0.61 M-v 3Ek MPCORBFIT  1804    (433) Eros'
             '               20260919\n')
APOLLO_LINE = ('01862   16.09  0.09 K2669 224.36160  286.09771   35.50297    6.35218  0.5601800  0.55260044'
               '   1.4707151  0 E2026-QB8  3363  37 1930-2026 0.78 M-v 3Ek MPCORBFIT  9803   (1862) Apollo'
               '             20260415\n')
UK_2026_LINE = ('K26U00K 24.83  0.15 K2669 300.38854  332.63967   25.95305   25.31494  0.3323015  0.54778819'
                '   1.4793159  7 E2026-U44    20   1    1 days 0.49 M-v 3Ek MPCORBFIT  0803          2026 UK'
                '            20261019\n')

CAD_FIELDS = ['des', 'orbit_id', 'jd', 'cd', 'dist', 'dist_min', 'dist_max', 'v_rel', 'v_inf', 't_sigma_f', 'h',
              'fullname']


def _cad_row(des, jd, dist, h):
    return [des, '2', str(jd), '2026-Oct-19 04:38', str(dist), str(dist * 0.99), str(dist * 1.01), '15.1', '15.0',
            '00:01', str(h), '       ({})'.format(des)]


def _cad_payload(rows):
    return {'signature': {'source': 'NASA/JPL SBDB Close Approach Data API', 'version': '1.5'},
            'count': str(len(rows)), 'fields': CAD_FIELDS, 'data': rows}


class HexFlagsTestCase(unittest.TestCase):
    def test_real_mpcorb_flags(self):
        self.assertEqual(parse_mpc_hex_flags('1804'), (4, True, False))   # Eros: Amor, NEO >= 1 km
        self.assertEqual(parse_mpc_hex_flags('9803'), (3, True, True))    # Apollo: Apollo, PHA
        self.assertEqual(parse_mpc_hex_flags('8802'), (2, True, True))    # Apophis: Aten, PHA
        self.assertEqual(parse_mpc_hex_flags('1801'), (1, True, False))   # Atira
        self.assertEqual(parse_mpc_hex_flags('0000'), (None, False, False))
        self.assertEqual(parse_mpc_hex_flags(None), (None, False, False))
        self.assertEqual(parse_mpc_hex_flags('zz'), (None, False, False))


class ParseCloseApproachesTestCase(unittest.TestCase):
    def test_converts_tdb_to_utc(self):
        # JD 2461332.693197142 TDB = 2026-10-19 04:38:12.2 TDB; UTC is 69.18 s earlier.
        approaches = parse_close_approaches(_cad_payload([_cad_row('2026 UK', 2461332.693197142, 0.0195, 25.014)]))

        self.assertEqual(len(approaches), 1)
        delta = approaches[0]['approach_time'] - datetime(2026, 10, 19, 4, 37, 3, 50000)
        self.assertLess(abs(delta.total_seconds()), 0.5)
        self.assertIsNone(approaches[0]['approach_time'].tzinfo)
        self.assertEqual(approaches[0]['designation'], '2026 UK')
        self.assertAlmostEqual(approaches[0]['dist_au'], 0.0195)
        self.assertAlmostEqual(approaches[0]['h'], 25.014)
        self.assertAlmostEqual(approaches[0]['v_rel_kms'], 15.1)

    def test_valid_empty_response(self):
        self.assertEqual(parse_close_approaches({'signature': {}, 'count': 0}), [])

    def test_invalid_responses_raise(self):
        invalid = [
            None,
            {'error': 'bad request'},
            {'signature': {}, 'count': 'x'},
            {'signature': {}, 'count': '1', 'fields': ['des'], 'data': [['433']]},
            _cad_payload([_cad_row('433', 2461332.7, 0.02, 18.0)]) | {'count': '2'},
            _cad_payload([_cad_row('433', 'not-a-jd', 0.02, 18.0)]),
            _cad_payload([['433']]),
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(CloseApproachSourceError):
                    parse_close_approaches(payload)

    def test_missing_h_is_allowed(self):
        row = _cad_row('433', 2461332.7, 0.02, 18.0)
        row[CAD_FIELDS.index('h')] = None
        self.assertIsNone(parse_close_approaches(_cad_payload([row]))[0]['h'])


class EstimatePeakMagTestCase(unittest.TestCase):
    def test_estimate(self):
        self.assertAlmostEqual(estimate_peak_mag(25.0, 0.0195), 16.45, places=2)
        self.assertIsNone(estimate_peak_mag(None, 0.02))
        self.assertIsNone(estimate_peak_mag(20.0, 0.0))


class NeoDbTestCase(unittest.TestCase):
    # The synthetic approaches below do not match the real orbits, so by default the peak
    # computed from the orbit is disabled and selection falls back to the rough estimate.
    real_peak_brightness = False

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.excerpt_file = os.path.join(self.tmp_dir.name, 'MPCORB.9999.DAT')
        self.nea_file = os.path.join(self.tmp_dir.name, 'NEA.txt')
        with open(self.excerpt_file, 'w', encoding='ascii') as f:
            f.writelines([CERES_LINE])
        with open(self.nea_file, 'w', encoding='ascii') as f:
            f.writelines([EROS_LINE, APOLLO_LINE, UK_2026_LINE])
        self.patches = [
            patch.object(minor_planet_utils, 'MPCORB_EXCERPT_FILE', self.excerpt_file),
            patch.object(minor_planet_utils, 'NEA_FILE', self.nea_file),
        ]
        if not self.real_peak_brightness:
            self.patches.append(patch.object(neo_utils, 'compute_peak_brightness', return_value=(None, None)))
        for p in self.patches:
            p.start()
        minor_planet_utils.reset_minor_planets_cache()
        self.window_start = datetime(2026, 10, 19, 0, 0)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        minor_planet_utils.reset_minor_planets_cache()
        self.tmp_dir.cleanup()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _approach(self, designation, days=1.0, dist_au=0.02, h=20.0):
        return {
            'designation': designation,
            'approach_time': self.window_start + timedelta(days=days),
            'dist_au': dist_au, 'dist_min_au': dist_au, 'dist_max_au': dist_au,
            'v_rel_kms': 10.0, 'h': h, 't_sigma': '00:01', 'orbit_id': '1',
        }


class PeakBrightnessTestCase(NeoDbTestCase):
    real_peak_brightness = True

    def _uk_approach(self):
        # Real CNEOS approach of 2026 UK: 2026-10-19 04:37 UTC at 0.01947 au, H 25.0.
        return self._approach('2026 UK', h=25.014, dist_au=0.01947) | {
            'approach_time': datetime(2026, 10, 19, 4, 37, 3)}

    def test_vectorized_magnitude_matches_scalar_model(self):
        for r, delta, earth_sun in [(1.0, 0.02, 0.99), (1.2, 0.3, 1.0), (1.01, 0.05, 0.995)]:
            self.assertAlmostEqual(
                float(neo_utils.apparent_magnitude_hg(20.0, 0.15, r, delta, earth_sun)),
                minor_planet_utils._get_apparent_magnitude_hg(20.0, 0.15, delta, r, earth_sun), places=6)

    def test_peak_of_real_approach(self):
        from skyfield.api import load
        mpc_row = minor_planet_utils.find_mpc_minor_planet('K26U00K')
        peak_mag, peak_time = neo_utils.compute_peak_brightness(
            mpc_row, datetime(2026, 10, 19, 4, 37, 3), load.timescale(builtin=True), load('de421.bsp'))

        # Phase makes it fainter than the rough estimate (~16.5) and the peak need not be at closest approach.
        self.assertGreater(peak_mag, estimate_peak_mag(25.014, 0.01947))
        self.assertLess(peak_mag, 18.0)
        self.assertLess(abs((peak_time - datetime(2026, 10, 19, 4, 37)).total_seconds()), 5 * 86400)
        self.assertEqual(peak_time.microsecond, 0)

    def test_store_saves_computed_peak_and_filters_by_it(self):
        store_close_approaches([self._uk_approach()], datetime(2026, 10, 19, 0, 0))
        approach = NeoCloseApproach.query.one()
        self.assertIsNotNone(approach.peak_mag)
        self.assertIsNotNone(approach.peak_time)
        self.assertEqual(approach.best_peak_mag(), approach.peak_mag)

        NeoCloseApproach.query.delete()
        db.session.commit()
        store_close_approaches([self._uk_approach()], datetime(2026, 10, 19, 0, 0),
                               mag_limit=approach.peak_mag - 0.1)
        # The rough estimate (~16.5) passes, the computed peak does not.
        self.assertEqual(NeoCloseApproach.query.count(), 0)

    def test_phase_geometry_is_one_consistent_triangle(self):
        import numpy as np
        from skyfield.api import load
        from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
        from skyfield.data import mpc
        ts, eph = load.timescale(builtin=True), load('de421.bsp')
        sun, earth = eph['sun'], eph['earth']
        body = sun + mpc.mpcorb_orbit(minor_planet_utils.find_mpc_minor_planet('K26U00K'), ts, GM_SUN)
        t = ts.utc(2026, 10, 19, np.arange(0, 24))

        r, delta, earth_sun = neo_utils._sun_earth_body_distances(body, t, sun, earth)

        # The phase angle from the three distances equals the angle between the vectors
        # from the asteroid to the Sun and to the Earth at the same instant.
        to_sun = sun.at(t).position.au - body.at(t).position.au
        to_earth = earth.at(t).position.au - body.at(t).position.au
        cos_vectors = np.sum(to_sun * to_earth, axis=0) / (np.linalg.norm(to_sun, axis=0) * np.linalg.norm(to_earth, axis=0))
        cos_distances = (r ** 2 + delta ** 2 - earth_sun ** 2) / (2 * r * delta)
        np.testing.assert_allclose(cos_distances, cos_vectors, atol=1e-9)

    def test_prefilter_uses_mpc_h_for_matched_asteroids(self):
        # CAD H much fainter than MPC H (24.83): the CAD-based estimate (~18.55) would drop it
        # before the peak (~17) is computed.
        store_close_approaches([self._uk_approach() | {'h': 27.1}], datetime(2026, 10, 19, 0, 0))
        approach = NeoCloseApproach.query.one()
        self.assertLess(approach.peak_mag, 18.0)
        mpc_h = minor_planet_utils.find_mpc_minor_planet('K26U00K')['magnitude_H']
        self.assertAlmostEqual(approach.est_peak_mag, estimate_peak_mag(mpc_h, 0.01947), places=6)

    def test_failed_peak_computation_falls_back_to_estimate(self):
        with patch.object(neo_utils, 'compute_peak_brightness', side_effect=RuntimeError('boom')):
            store_close_approaches([self._uk_approach()], datetime(2026, 10, 19, 0, 0))
        approach = NeoCloseApproach.query.one()
        self.assertIsNone(approach.peak_mag)
        self.assertEqual(approach.best_peak_mag(), approach.est_peak_mag)


class DiameterTestCase(unittest.TestCase):
    def test_diameter_range_from_h(self):
        self.assertEqual(NeoCloseApproach(h=22.0).diameter_range_str(), '110–240 m')  # PHA size limit ~140 m
        self.assertEqual(NeoCloseApproach(h=28.0).diameter_range_str(), '6.7–15 m')
        self.assertEqual(NeoCloseApproach(h=16.68).diameter_range_str(), '1.2–2.7 km')
        self.assertEqual(NeoCloseApproach(h=None).diameter_range_str(), '')

    def test_mpc_h_takes_precedence_over_cad_h(self):
        approach = NeoCloseApproach(h=27.1, minor_planet=MinorPlanet(magnitude_H=22.0))
        self.assertEqual(approach.abs_magnitude(), 22.0)
        self.assertEqual(approach.diameter_range_str(), '110–240 m')


class DesignationIndexTestCase(NeoDbTestCase):
    def test_numbered_and_provisional_designations(self):
        index = build_designation_index(minor_planet_utils.get_all_mpc_minor_planets())
        self.assertEqual(index['433'], '00433')
        self.assertEqual(index['2026 UK'], 'K26U00K')
        self.assertEqual(index['1'], '00001')


class StoreCloseApproachesTestCase(NeoDbTestCase):
    def test_imports_matched_keeps_unmatched_and_filters_faint(self):
        store_close_approaches([
            self._approach('2026 UK', h=24.8, dist_au=0.02),      # ~16.3 mag
            self._approach('2026 XX', h=22.0, dist_au=0.01),      # not in NEA.txt
            self._approach('1862', h=16.1, dist_au=0.04),         # ~9.1 mag
            self._approach('2026 YY', h=29.0, dist_au=0.05),      # ~22.5 mag, too faint
        ], self.window_start)

        approaches = {a.designation: a for a in NeoCloseApproach.query.all()}
        self.assertEqual(set(approaches), {'2026 UK', '2026 XX', '1862'})
        self.assertIsNone(approaches['2026 XX'].minor_planet_id)

        uk = approaches['2026 UK'].minor_planet
        self.assertEqual(uk.mpc_designation, 'K26U00K')
        self.assertTrue(uk.is_neo)
        self.assertEqual(uk.orbit_type, 3)
        self.assertTrue(approaches['1862'].minor_planet.is_pha)
        self.assertNotIn('2026 YY', approaches)

    def test_repeated_run_is_idempotent(self):
        approaches = [self._approach('2026 UK', h=24.8), self._approach('1862', h=16.1)]
        store_close_approaches(approaches, self.window_start)
        store_close_approaches(approaches, self.window_start)

        self.assertEqual(MinorPlanet.query.count(), 2)
        self.assertEqual(NeoCloseApproach.query.count(), 2)

    def test_reuses_existing_minor_planet_row(self):
        db.session.add(MinorPlanet(int_designation=1862, mpc_designation='01862', magnitude_H=99.0))
        db.session.commit()

        store_close_approaches([self._approach('1862', h=16.1)], self.window_start)

        self.assertEqual(MinorPlanet.query.count(), 1)
        self.assertEqual(MinorPlanet.query.one().magnitude_H, 16.09)

    def test_replaces_window_and_keeps_history(self):
        db.session.add_all([
            NeoCloseApproach(designation='OLD', approach_time=self.window_start - timedelta(days=1), dist_au=0.01),
            NeoCloseApproach(designation='STALE', approach_time=self.window_start + timedelta(days=2), dist_au=0.01),
            NeoCloseApproach(designation='LATER', approach_time=self.window_start + timedelta(days=61), dist_au=0.01),
        ])
        db.session.commit()

        store_close_approaches([self._approach('2026 UK', days=40, h=24.8)], self.window_start, days=60)

        self.assertEqual(sorted(a.designation for a in NeoCloseApproach.query.all()), ['2026 UK', 'LATER', 'OLD'])

    def test_drops_approaches_outside_window(self):
        store_close_approaches([
            self._approach('1862', days=-0.5, h=16.1),
            self._approach('2026 UK', days=61, h=24.8),
        ], self.window_start, days=60)
        self.assertEqual(NeoCloseApproach.query.count(), 0)

    def test_repeated_run_does_not_duplicate_with_moving_window(self):
        approaches = [self._approach('1862', days=1, h=16.1)]
        store_close_approaches(approaches, self.window_start)
        store_close_approaches(approaches, self.window_start + timedelta(hours=1))
        self.assertEqual(NeoCloseApproach.query.count(), 1)

    def test_fetch_uses_exact_window_bounds(self):
        response = unittest.mock.MagicMock()
        response.json.return_value = {'signature': {}, 'count': 0}
        with patch.object(neo_utils.requests, 'get', return_value=response) as get:
            self.assertEqual(neo_utils.fetch_close_approaches(datetime(2026, 10, 19, 20, 5, 12), days=60), [])
        params = get.call_args.kwargs['params']
        self.assertEqual(params['date-min'], '2026-10-19T20:05:12')
        self.assertEqual(params['date-max'], '2026-12-18T20:05:12')
        self.assertEqual(params['nea'], 'true')
        self.assertNotIn('neo', params)

    def test_failure_rolls_back_and_keeps_stored_approaches(self):
        store_close_approaches([self._approach('1862', h=16.1)], self.window_start)

        with patch.object(neo_utils, '_get_or_create_minor_planet', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                store_close_approaches([self._approach('2026 UK', h=24.8)], self.window_start)

        self.assertEqual([a.designation for a in NeoCloseApproach.query.all()], ['1862'])


class UpdateNeosTestCase(NeoDbTestCase):
    def setUp(self):
        super().setUp()
        self.side_patches = [
            patch.object(neo_utils, 'ensure_nea_file', return_value=self.nea_file),
            patch.object(neo_utils, 'update_neo_positions'),
            patch.object(neo_utils, '_utcnow', return_value=self.window_start),
        ]
        for p in self.side_patches:
            p.start()
        store_close_approaches([self._approach('1862', h=16.1)], self.window_start)

    def tearDown(self):
        for p in self.side_patches:
            p.stop()
        super().tearDown()

    def test_source_error_keeps_stored_approaches(self):
        with patch.object(neo_utils, 'fetch_close_approaches', side_effect=CloseApproachSourceError('down')):
            update_neos()
        self.assertEqual(NeoCloseApproach.query.count(), 1)
        neo_utils.update_neo_positions.assert_called_once_with(update_elements=True)

    def test_valid_empty_response_clears_window(self):
        with patch.object(neo_utils, 'fetch_close_approaches', return_value=[]):
            update_neos()
        self.assertEqual(NeoCloseApproach.query.count(), 0)

    def test_always_forces_nea_download(self):
        with patch.object(neo_utils, 'fetch_close_approaches', return_value=[]):
            update_neos()
        neo_utils.ensure_nea_file.assert_called_once_with(force_reload=True)

    def test_held_lock_skips_update_unless_forced(self):
        with patch.object(neo_utils, 'fetch_close_approaches', return_value=[]) as fetch:
            self.assertTrue(update_neos())
            self.assertFalse(update_neos())  # e.g. CLI while the scheduled run holds the lock
            self.assertEqual(fetch.call_count, 1)
            self.assertTrue(update_neos(force=True))
            self.assertEqual(fetch.call_count, 2)


class UpdateNeoPositionsTestCase(NeoDbTestCase):
    def test_updates_only_near_earth_asteroids(self):
        db.session.add_all([
            MinorPlanet(int_designation=1, mpc_designation='00001', magnitude_H=3.33, magnitude_G=0.15),
            MinorPlanet(int_designation=433, mpc_designation='00433', magnitude_H=99.0, magnitude_G=0.15,
                        hex_flags='1804', is_neo=True),
        ])
        db.session.commit()

        with patch.object(minor_planet_utils, 'load_constellation_map', return_value=lambda position: None):
            minor_planet_utils.update_neo_positions(update_elements=True)

        ceres = MinorPlanet.query.filter_by(mpc_designation='00001').one()
        eros = MinorPlanet.query.filter_by(mpc_designation='00433').one()
        self.assertIsNone(ceres.cur_ra)
        self.assertIsNotNone(eros.cur_ra)
        self.assertIsNotNone(eros.eval_mag)
        self.assertEqual(eros.magnitude_H, 10.39)  # elements refreshed from NEA.txt


class MinorPlanetsChartSceneTestCase(NeoDbTestCase):
    def test_neo_uses_current_position_others_stored_position(self):
        db.session.add_all([
            MinorPlanet(int_designation=1, mpc_designation='00001', designation='(1) Ceres', eval_mag=8.0,
                        cur_ra=1.0, cur_dec=0.1),
            MinorPlanet(int_designation=433, mpc_designation='00433', designation='(433) Eros', eval_mag=10.0,
                        cur_ra=1.0, cur_dec=0.1, is_neo=True),
        ])
        db.session.commit()

        views = 'app.main.solarsystem.minor_planet_views'
        with patch(views + '.build_scene_v1', return_value={}), \
                patch(views + '.resolve_chart_city_lat_lon', return_value=('Prague', 50.0, 14.4)):
            scene = self.app.test_client().get('/minor-planets/chart/scene-v1?dt=2027-01-01T20:00:00Z').get_json()

        positions = {h['label']: (h['ra'], h['dec']) for h in scene['objects']['highlights']}
        self.assertEqual(positions['(1) Ceres'], (1.0, 0.1))
        eros = MinorPlanet.query.filter_by(mpc_designation='00433').one()
        expected = minor_planet_utils.get_minor_planet_radec(
            eros, datetime(2027, 1, 1, 20, 0, tzinfo=timezone.utc), observer_lat=50.0, observer_lon=14.4)
        # The scene rounds coordinates to 6 decimals.
        self.assertAlmostEqual(positions['(433) Eros'][0], expected[0], places=5)
        self.assertAlmostEqual(positions['(433) Eros'][1], expected[1], places=5)


class MinorPlanetsListOrbitFilterTestCase(NeoDbTestCase):
    def test_orbit_group_filter(self):
        db.session.add_all([
            MinorPlanet(int_designation=1, mpc_designation='00001', designation='(1) Ceres', eval_mag=8.0),
            MinorPlanet(int_designation=433, mpc_designation='00433', designation='(433) Eros', eval_mag=10.0,
                        is_neo=True),
        ])
        db.session.commit()
        client = self.app.test_client()

        def listed(orbit_group):
            html = client.post('/minor-planets', data={'orbit_group': orbit_group, 'season': 'All',
                                                       'items_per_page': '25'},
                               follow_redirects=True).get_data(as_text=True)
            return [name for name in ('(1) Ceres', '(433) Eros') if name in html]

        self.assertEqual(listed('neo'), ['(433) Eros'])
        self.assertEqual(listed('not_neo'), ['(1) Ceres'])
        self.assertEqual(listed('all'), ['(1) Ceres', '(433) Eros'])


class MinorPlanetDetailNeoTestCase(NeoDbTestCase):
    def test_detail_shows_neo_block_and_approaches_without_computed_values(self):
        now = datetime.utcnow()
        store_close_approaches([self._approach('1862', h=16.1, dist_au=0.005)
                                | {'approach_time': now + timedelta(days=3)}], now)

        response = self.app.test_client().get('/minor-planet/1862/catalogue_data')

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('PHA', html)
        self.assertIn('Apollo', html)
        self.assertIn('{:.1f} LD'.format(0.005 * 149597870.7 / 384400.0), html)
        self.assertIn('exclamation triangle', html)  # very close approach warning


class NearEarthAsteroidsViewTestCase(NeoDbTestCase):
    def test_page_lists_upcoming_approaches(self):
        now = datetime.utcnow()
        store_close_approaches([
            self._approach('1862', h=16.1) | {'approach_time': now + timedelta(days=3)},
            self._approach('2026 XX', h=22.0, dist_au=0.001) | {'approach_time': now + timedelta(days=5)},
            self._approach('2026 UK', h=24.8) | {'approach_time': now + timedelta(days=50)},
        ], now)

        client = self.app.test_client()
        html = client.get('/near-earth-asteroids?period=30').get_data(as_text=True)
        self.assertIn('(1862) Apollo', html)
        self.assertIn('2026 XX', html)
        self.assertNotIn('2026 UK', html)

        html = client.get('/near-earth-asteroids?period=60&pha_only=y').get_data(as_text=True)
        self.assertIn('(1862) Apollo', html)
        self.assertNotIn('2026 XX', html)

    def _store_sort_fixture(self):
        now = datetime.utcnow()
        store_close_approaches([
            # 1862 Apollo: ~9.1 mag, in 10 days; 2026 UK: ~16.3 mag, in 2 days; 2026 XX unmatched: ~12 mag, in 5 days
            self._approach('1862', h=16.1, dist_au=0.04) | {'approach_time': now + timedelta(days=10)},
            self._approach('2026 UK', h=24.8, dist_au=0.02) | {'approach_time': now + timedelta(days=2)},
            self._approach('2026 XX', h=22.0, dist_au=0.01) | {'approach_time': now + timedelta(days=5)},
        ], now)
        db.session.query(MinorPlanet).filter_by(mpc_designation='K26U00K').update({'eval_mag': 19.0})
        db.session.query(MinorPlanet).filter_by(mpc_designation='01862').update({'eval_mag': 15.0})
        db.session.commit()

    def _listed_order(self, query=''):
        # maglim= clears the default 16 mag limit, so all three fixtures are listed.
        html = self.app.test_client().get('/near-earth-asteroids?period=30&maglim=' + query).get_data(as_text=True)
        tbody = html[html.index('<tbody>'):]
        return sorted(['(1862) Apollo', '2026 UK', '2026 XX'], key=tbody.index)

    def test_default_sort_is_brightest_first(self):
        self._store_sort_fixture()
        self.assertEqual(self._listed_order(), ['(1862) Apollo', '2026 XX', '2026 UK'])

    def test_default_limit_is_16_mag_and_can_be_cleared(self):
        self._store_sort_fixture()
        client = self.app.test_client()
        tbody = lambda url: (lambda html: html[html.index('<tbody>'):])(client.get(url).get_data(as_text=True))

        default = tbody('/near-earth-asteroids?period=30')
        self.assertIn('(1862) Apollo', default)
        self.assertNotIn('2026 UK', default)  # ~16.3 mag
        self.assertIn('2026 UK', tbody('/near-earth-asteroids?period=30&maglim='))

    def test_cleared_limit_survives_sorting(self):
        self._store_sort_fixture()
        html = self.app.test_client().get('/near-earth-asteroids?period=30&maglim=').get_data(as_text=True)
        link = html[html.index('sortby=date') - 200:html.index('sortby=date') + 200]
        self.assertRegex(link, r'sortby=date[^"]*maglim="')

    def test_columns_are_grouped_now_peak_approach(self):
        self._store_sort_fixture()
        html = self.app.test_client().get('/near-earth-asteroids?period=30&maglim=').get_data(as_text=True)
        header = html[html.index('<thead>'):html.index('</thead>')]
        order = ['name', 'cur_mag', 'peak_mag', 'peak_time', 'date', 'dist', 'v_rel', 'size']
        # The current sort column links to the reversed direction ('-peak_mag').
        position = lambda column: header.index('sortby=' + column) if 'sortby=' + column in header \
            else header.index('sortby=-' + column)
        self.assertEqual(sorted(order, key=position), order)
        self.assertLess(header.index('Teď') if 'Teď' in header else header.index('Now'),
                        header.index('Průlet') if 'Průlet' in header else header.index('Approach'))
        tbody = html[html.index('<tbody>'):]
        self.assertIn('km', tbody.split('(1862) Apollo', 1)[1].split('</tr>', 1)[0])  # Apollo H 16.1 -> km size

    def test_sort_by_size_largest_first(self):
        self._store_sort_fixture()
        # MPC H: Apollo 16.09, 2026 UK 24.83; unmatched 2026 XX CAD H 22.0
        self.assertEqual(self._listed_order('&sortby=size'), ['(1862) Apollo', '2026 XX', '2026 UK'])

    def test_sortable_columns(self):
        self._store_sort_fixture()
        self.assertEqual(self._listed_order('&sortby=date'), ['2026 UK', '2026 XX', '(1862) Apollo'])
        self.assertEqual(self._listed_order('&sortby=-date'), ['(1862) Apollo', '2026 XX', '2026 UK'])
        self.assertEqual(self._listed_order('&sortby=dist'), ['2026 XX', '2026 UK', '(1862) Apollo'])
        self.assertEqual(self._listed_order('&sortby=name'), ['(1862) Apollo', '2026 UK', '2026 XX'])
        # The unmatched asteroid has no current brightness and stays last in both directions.
        self.assertEqual(self._listed_order('&sortby=cur_mag'), ['(1862) Apollo', '2026 UK', '2026 XX'])
        self.assertEqual(self._listed_order('&sortby=-cur_mag'), ['2026 UK', '(1862) Apollo', '2026 XX'])
        self.assertEqual(self._listed_order('&sortby=bogus'), self._listed_order())

    def test_sort_links_keep_filters(self):
        self._store_sort_fixture()
        html = self.app.test_client().get('/near-earth-asteroids?period=7&dist_max_ld=10&pha_only=y').get_data(
            as_text=True)
        self.assertIn('sortby=date', html)
        link = html[html.index('sortby=date') - 200:html.index('sortby=date') + 200]
        for arg in ('period=7', 'dist_max_ld=10', 'pha_only=y'):
            self.assertIn(arg, link)
        self.assertIn('name="sortby" value="peak_mag"', html)
        # Server-side sorting only: the 'sortable' class would also enable client-side tablesort.
        table_tag = html[html.index('<table'):html.index('>', html.index('<table'))]
        self.assertNotIn('sortable', table_tag)

    def test_distance_all_is_a_selectable_choice(self):
        self._store_sort_fixture()
        client = self.app.test_client()

        html = client.get('/near-earth-asteroids').get_data(as_text=True)
        self.assertRegex(html, r'<option selected value="all">|<option value="all" selected>')
        self.assertEqual(self._listed_order('&dist_max_ld=all'), self._listed_order())
        self.assertEqual(len(self._listed_order('&dist_max_ld=')), 3)  # old empty value still works
        html = client.get('/near-earth-asteroids?dist_max_ld=5').get_data(as_text=True)
        self.assertNotIn('(1862) Apollo', html[html.index('<tbody>'):])  # 0.04 au ~ 15.6 LD

    def test_invalid_filter_values_fall_back_to_defaults(self):
        now = datetime.utcnow()
        store_close_approaches([self._approach('1862', h=16.1) | {'approach_time': now + timedelta(days=3)}], now)

        response = self.app.test_client().get('/near-earth-asteroids?dist_max_ld=invalid&period=999&maglim=x')

        self.assertEqual(response.status_code, 200)
        self.assertIn('(1862) Apollo', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
