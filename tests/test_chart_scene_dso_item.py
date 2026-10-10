import math
import unittest
from types import SimpleNamespace

from app.commons.chart_scene import build_scene_dso_item_from_model


class BuildSceneDsoItemFromModelTestCase(unittest.TestCase):
    def test_axes_and_position_angle_converted(self):
        dso = SimpleNamespace(name='UGC12506', type='GX', ra=1.0, dec=0.5, mag=15.0,
                              major_axis=102.0, minor_axis=24.0, position_angle=81.0)
        item = build_scene_dso_item_from_model(dso)
        self.assertAlmostEqual(item['rlong_rad'], math.radians(102.0 / 3600.0) / 2.0, places=6)
        self.assertAlmostEqual(item['rshort_rad'], math.radians(24.0 / 3600.0) / 2.0, places=6)
        self.assertAlmostEqual(item['position_angle_rad'], math.radians(81.0), places=3)

    def test_missing_axes_and_position_angle(self):
        dso = SimpleNamespace(name='X1', type='GX', ra=1.0, dec=0.5, mag=None,
                              major_axis=None, minor_axis=0.0, position_angle=None)
        item = build_scene_dso_item_from_model(dso)
        self.assertEqual(item['rlong_rad'], -1.0)
        self.assertEqual(item['rshort_rad'], -1.0)
        self.assertAlmostEqual(item['position_angle_rad'], math.pi * 0.5)


if __name__ == '__main__':
    unittest.main()
