import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.main.solarsystem.comet_views import comets_chart_scene_v1


class _DummyCometQuery:
    def __init__(self, comets):
        self.comets = comets

    def filter(self, *args):
        return self

    def all(self):
        return self.comets


class CometsSceneTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')

    def test_scene_payload_contains_visible_comet_highlights(self):
        comets = [
            SimpleNamespace(
                id=1,
                designation='C/2026 A1',
                real_mag=12.3,
                cur_ra=1.2,
                cur_dec=0.3,
                cur_tail_pa=0.7,
            ),
            SimpleNamespace(
                id=2,
                designation='C/2026 B2',
                real_mag=17.2,
                cur_ra=2.4,
                cur_dec=-0.1,
                cur_tail_pa=None,
            ),
        ]
        scene = {'version': 'scene-v1', 'meta': {}, 'objects': {}}

        url = '/comets/chart/scene-v1?ra=1.2&dec=0.3&fsz=23&width=800&height=600'
        with self.app.test_request_context(url), \
             patch('app.main.solarsystem.comet_views.Comet.query',
                   _DummyCometQuery(comets)), \
             patch('app.main.solarsystem.comet_views.get_fld_size_mags_from_request',
                   return_value=(23.0, 'FoV: 23', 8.0, 16.0)), \
             patch('app.main.solarsystem.comet_views.build_scene_v1',
                   return_value=scene):
            response = comets_chart_scene_v1()

        payload = response.get_json()
        highlights = payload['objects']['highlights']
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0]['shape'], 'comet')
        self.assertEqual(highlights[0]['id'], '_com_1')
        self.assertEqual(highlights[0]['label'], 'C/2026 A1')
        self.assertEqual(highlights[0]['mag'], 12.3)
        self.assertEqual(highlights[0]['tail_pa'], 0.7)
        self.assertEqual(payload['meta']['object_context']['kind'], 'comets')
        self.assertEqual(payload['meta']['object_context']['count'], 1)


if __name__ == '__main__':
    unittest.main()
