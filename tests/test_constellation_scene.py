import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.main.catalogue.constellation_views import constellation_chart_scene_v1


class ConstellationSceneTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')

    def test_scene_payload_marks_highlighted_constellation(self):
        constellation = SimpleNamespace(
            iau_code='ori',
            name='Orion',
            label_ra=1.23,
            label_dec=-0.45,
        )

        url = '/constellation/ori/chart/scene-v1?ra=1.23&dec=-0.45&fsz=23&width=800&height=600'
        scene = {'version': 'scene-v1', 'meta': {}}
        with self.app.test_request_context(url), \
             patch('app.main.catalogue.constellation_views._find_constellation',
                   return_value=constellation), \
             patch('app.main.catalogue.constellation_views._get_constellation_common_name',
                   return_value='Hunter'), \
             patch('app.main.catalogue.constellation_views.build_scene_v1',
                   return_value=scene):
            response = constellation_chart_scene_v1('ori')

        payload = response.get_json()
        self.assertEqual(payload['meta']['highlight_constellation'], 'ORI')
        self.assertEqual(payload['meta']['object_context']['kind'], 'constellation')
        self.assertEqual(payload['meta']['object_context']['id'], 'ori')
        self.assertEqual(payload['meta']['object_context']['label'], 'Hunter')
        self.assertEqual(payload['meta']['object_context']['ra'], 1.23)
        self.assertEqual(payload['meta']['object_context']['dec'], -0.45)


if __name__ == '__main__':
    unittest.main()
