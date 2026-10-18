import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from app import create_app
from app.commons import online_trajectory as ot

COMET_VIEWS = 'app.main.solarsystem.comet_views'
MINOR_PLANET_VIEWS = 'app.main.solarsystem.minor_planet_views'

COMET = pd.Series({
    'designation': 'C/2026 T1 (Test)', 'comet_id': 'C2026T1', 'perihelion_year': 2026, 'perihelion_month': 9,
    'perihelion_day': 20.125, 'perihelion_distance_au': 0.8, 'eccentricity': 0.99, 'inclination_degrees': 45.0,
    'longitude_of_ascending_node_degrees': 120.0, 'argument_of_perihelion_degrees': 70.0, 'mag': 9.5,
})

CERES = pd.Series({
    'designation': '(1) Ceres', 'designation_packed': '00001', 'epoch_packed': 'K25BL',
    'semimajor_axis_au': 2.7666, 'eccentricity': 0.0796, 'inclination_degrees': 10.588,
    'longitude_of_ascending_node_degrees': 80.25, 'argument_of_perihelion_degrees': 73.3,
    'mean_anomaly_degrees': 231.5,
})

MINOR_PLANET = SimpleNamespace(id=1, designation='(1) Ceres', int_designation=1, mpc_designation=None,
                               url_id=lambda: '1')


def _scene():
    return {'version': 'scene-v1', 'meta': {}, 'objects': {}}


@unittest.skipUnless(os.path.exists('de421.bsp'), 'needs local de421.bsp')
class OnlineTrajectoryViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        ot.clear_trajectory_cache()
        self.patches = [
            patch(COMET_VIEWS + '.find_mpc_comet', side_effect=lambda cid: COMET if cid == 'C2026T1' else None),
            patch(COMET_VIEWS + '.build_scene_v1', side_effect=_scene),
            patch(MINOR_PLANET_VIEWS + '._get_minor_planet_by_url_id',
                  side_effect=lambda mid: MINOR_PLANET if mid == '1' else None),
            patch(MINOR_PLANET_VIEWS + '.find_mpc_minor_planet', return_value=CERES),
            patch(MINOR_PLANET_VIEWS + '.build_scene_v1', side_effect=_scene),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        ot.clear_trajectory_cache()

    def test_comet_scene_has_descriptor_without_points(self):
        response = self.client.get('/comet/C2026T1/chart/scene-v1?traj_from=2026-09-01&traj_to=2026-10-01')
        self.assertEqual(response.status_code, 200)
        scene = response.get_json()
        descriptor = scene['meta']['trajectory_source']
        self.assertEqual(descriptor['url'], '/comet/C2026T1/chart/trajectory-v1')
        self.assertEqual((descriptor['traj_from'], descriptor['traj_to']), ('2026-09-01', '2026-10-01'))
        self.assertTrue(descriptor['request_key'] and descriptor['revision'])
        self.assertEqual(scene['objects']['trajectories'], [])

    def test_scene_without_or_with_invalid_interval_has_no_descriptor(self):
        for query in ('', '?traj_from=2026-10-01&traj_to=2026-09-01', '?traj_from=bad&traj_to=2026-09-01'):
            with self.subTest(query=query):
                response = self.client.get('/comet/C2026T1/chart/scene-v1' + query)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.get_json()['meta']['trajectory_source'])

    def test_scene_does_not_run_sampler(self):
        with patch.object(ot, 'compute_trajectory_payload', side_effect=AssertionError('sampler called')):
            response = self.client.get('/comet/C2026T1/chart/scene-v1?traj_from=2026-09-01&traj_to=2026-10-01')
        self.assertEqual(response.status_code, 200)

    def test_comet_trajectory_endpoint(self):
        scene = self.client.get('/comet/C2026T1/chart/scene-v1?traj_from=2026-09-01&traj_to=2026-10-01').get_json()
        descriptor = scene['meta']['trajectory_source']
        response = self.client.get(descriptor['url'] + '?traj_from=2026-09-01&traj_to=2026-10-01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-cache')
        payload = response.get_json()
        self.assertEqual(payload['version'], 'trajectory-v1')
        self.assertEqual(payload['request_key'], descriptor['request_key'])
        self.assertEqual(payload['revision'], descriptor['revision'])
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['tolerance_arcsec'], 10)
        trajectory = payload['trajectory']
        self.assertEqual((trajectory['id'], trajectory['type'], trajectory['label']),
                         ('COMET_TRAJ_C2026T1', 'comet', 'C/2026 T1 (Test)'))
        labeled = [p for p in trajectory['points'] if p['label']]
        self.assertEqual(labeled[0]['label'], '01.09.')
        self.assertTrue(all(p['sun_ra'] is not None for p in labeled))
        self.assertGreater(len(trajectory['points']), len(labeled))

    def test_trajectory_endpoint_uses_cache(self):
        url = '/comet/C2026T1/chart/trajectory-v1?traj_from=2026-09-01&traj_to=2026-10-01'
        first = self.client.get(url).get_json()
        with patch.object(ot, '_skyfield_context', side_effect=AssertionError('ephemeris used')):
            second = self.client.get(url).get_json()
        self.assertEqual(first, second)

    def test_trajectory_endpoint_errors(self):
        cases = {
            '/comet/C2026T1/chart/trajectory-v1?traj_from=2026-10-01&traj_to=2026-09-01': 400,
            '/comet/C2026T1/chart/trajectory-v1?traj_from=2026-09-01': 400,
            '/comet/unknown/chart/trajectory-v1?traj_from=2026-09-01&traj_to=2026-10-01': 404,
            '/comet/C2026T1/chart/trajectory-v1?traj_from=2200-01-01&traj_to=2200-02-01': 422,
            '/minor-planet/999/chart/trajectory-v1?traj_from=2026-09-01&traj_to=2026-10-01': 404,
        }
        for url, status in cases.items():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

    def test_minor_planet_scene_and_trajectory(self):
        scene = self.client.get('/minor-planet/1/chart/scene-v1?traj_from=2026-01-01&traj_to=2026-02-01').get_json()
        descriptor = scene['meta']['trajectory_source']
        self.assertEqual(descriptor['url'], '/minor-planet/1/chart/trajectory-v1')
        self.assertEqual(scene['objects']['trajectories'], [])
        payload = self.client.get(descriptor['url'] + '?traj_from=2026-01-01&traj_to=2026-02-01').get_json()
        self.assertEqual(payload['request_key'], descriptor['request_key'])
        trajectory = payload['trajectory']
        self.assertEqual(trajectory['id'], 'MINOR_PLANET_TRAJ_1')
        self.assertEqual(trajectory['type'], 'minor_planet')
        self.assertTrue(all(p['sun_ra'] is None for p in trajectory['points']))
        # Topocentric base grid of 6 hours.
        self.assertGreaterEqual(len(trajectory['points']), 31 * 4 + 1)

    def test_minor_planet_observer_is_part_of_request_key(self):
        url = '/minor-planet/1/chart/scene-v1?traj_from=2026-01-01&traj_to=2026-02-01'
        with patch(MINOR_PLANET_VIEWS + '.resolve_chart_city_lat_lon', return_value=('A', 50.0, 14.0)):
            key_a = self.client.get(url).get_json()['meta']['trajectory_source']['request_key']
        with patch(MINOR_PLANET_VIEWS + '.resolve_chart_city_lat_lon', return_value=('B', 49.0, 16.0)):
            key_b = self.client.get(url).get_json()['meta']['trajectory_source']['request_key']
        self.assertNotEqual(key_a, key_b)

    def test_comet_pdf_does_not_use_online_service(self):
        captured = {}

        def fake_pdf(obj_ra, obj_dec, trajectory=None, **kwargs):
            captured['trajectory'] = trajectory
            return io.BytesIO(b'%PDF-1.4')

        with patch(COMET_VIEWS + '.common_chart_pdf_img', side_effect=fake_pdf), \
                patch.object(ot, 'get_trajectory_payload', side_effect=AssertionError('online service used')), \
                patch.object(ot, 'compute_trajectory_payload', side_effect=AssertionError('online service used')):
            response = self.client.get('/comet/C2026T1/chart-pdf?traj_from=2026-09-01&traj_to=2026-10-01')
        self.assertEqual(response.status_code, 200)
        from fchart3.trajectory import RefinableTrajectory
        self.assertIsInstance(captured['trajectory'], RefinableTrajectory)


class InfoTemplatesTestCase(unittest.TestCase):
    def test_info_templates_send_interval_not_points(self):
        base = os.path.join(os.path.dirname(__file__), '..', 'app', 'templates', 'main', 'solarsystem')
        for name in ('comet_info.html', 'minor_planet_info.html'):
            with self.subTest(template=name):
                with open(os.path.join(base, name), encoding='utf-8') as f:
                    text = f.read()
                self.assertNotIn('trajectory=trajectory', text)
                self.assertEqual(text.count('traj_from=traj_from, traj_to=traj_to'), 2)


if __name__ == '__main__':
    unittest.main()
