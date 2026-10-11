import math
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd

from app import create_app, db
from app.commons import comet_utils
from app.commons.comet_utils import evaluate_comet_magnitude
from app.commons.light_curve_utils import (
    DEFAULT_LIGHT_CURVE_RANGE,
    comet_magnitude,
    create_light_curve_svg,
    hg_magnitude,
    light_curve_dates,
    parse_light_curve_range,
)
from app.commons.minor_planet_utils import _get_apparent_magnitude_hg
from app.models import Comet, CometObservation, MinorPlanet, Role
from config import TestingConfig


class LightCurveMathTestCase(unittest.TestCase):
    def test_hg_magnitude_matches_scalar_implementation(self):
        for r, delta, earth_sun in ((2.5, 1.6, 1.0), (1.2, 0.3, 0.99), (3.1, 3.8, 1.01)):
            cos_phase = (r ** 2 + delta ** 2 - earth_sun ** 2) / (2 * r * delta)
            phase = math.degrees(math.acos(cos_phase))
            expected = _get_apparent_magnitude_hg(5.2, 0.32, delta, r, earth_sun)
            actual = hg_magnitude(5.2, 0.32, np.array([r]), np.array([delta]), np.array([phase]))[0]
            self.assertAlmostEqual(expected, actual, places=6)

    def test_hg_magnitude_uses_default_slope_when_missing(self):
        args = (np.array([2.0]), np.array([1.0]), np.array([10.0]))
        self.assertEqual(hg_magnitude(7.0, None, *args)[0], hg_magnitude(7.0, 0.15, *args)[0])

    def test_comet_magnitude_matches_scalar_implementation(self):
        comet = Comet(magnitude_g=8.5, magnitude_k=4.0)
        expected = evaluate_comet_magnitude(comet, 1.3, 0.9)
        self.assertAlmostEqual(expected, comet_magnitude(8.5, 4.0, np.array([0.9]), np.array([1.3]))[0])

    def test_parse_light_curve_range(self):
        self.assertEqual(365, parse_light_curve_range('365'))
        self.assertEqual(DEFAULT_LIGHT_CURVE_RANGE, parse_light_curve_range('17'))
        self.assertEqual(DEFAULT_LIGHT_CURVE_RANGE, parse_light_curve_range(None))
        self.assertEqual(DEFAULT_LIGHT_CURVE_RANGE, parse_light_curve_range('abc'))

    def test_light_curve_dates_cover_symmetric_range(self):
        center = datetime(2026, 1, 1, tzinfo=timezone.utc)
        dates = light_curve_dates(center, 90)
        self.assertEqual(center - timedelta(days=90), dates[0])
        self.assertEqual(center + timedelta(days=90), dates[-1])

    def test_svg_skips_non_finite_magnitudes(self):
        dates = light_curve_dates(datetime(2026, 1, 1, tzinfo=timezone.utc), 90)
        mags = np.linspace(10, 12, len(dates))
        mags[:10] = np.nan
        svg = create_light_curve_svg(dates, mags, cursor_dt=dates[50], observations=[(dates[60], 11.0)],
                                     observations_label='COBS')
        self.assertTrue(svg.lstrip().startswith('<?xml'))


class LightCurveViewsTestCase(unittest.TestCase):
    def setUp(self):
        with patch.multiple(TestingConfig, SQLALCHEMY_DATABASE_URI='sqlite://',
                            SQLALCHEMY_BINDS={'sqm_sql': 'sqlite://'}):
            self.app = create_app('testing', default_locale='en')
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

    def tearDown(self):
        comet_utils._get_comet_cached.cache_clear()
        db.session.remove()
        db.drop_all()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()

    def _create_comet(self, **overrides):
        values = dict(comet_id='manual-light-curve', designation='Light curve comet', is_manual=True,
                      perihelion_year=2026, perihelion_month=9, perihelion_day=20.125, perihelion_distance_au=0.8,
                      eccentricity=1.0, inclination_degrees=45.0, longitude_of_ascending_node_degrees=120.0,
                      argument_of_perihelion_degrees=70.0, magnitude_g=8.0, magnitude_k=4.0)
        values.update(overrides)
        comet = Comet(**values)
        db.session.add(comet)
        db.session.commit()
        return comet

    def test_comet_light_curve_page_and_image(self):
        comet = self._create_comet()
        db.session.add(CometObservation(comet_id=comet.id, date=datetime(2026, 9, 1), mag=9.0))
        db.session.commit()

        response = self.client.get('/comet/{}/light-curve?range=365'.format(comet.comet_id))
        self.assertEqual(200, response.status_code)
        self.assertIn(b'light-curve-img', response.data)

        response = self.client.get('/comet/{}/light-curve-img?range=90&dt=2026-09-20T00:00:00'.format(comet.comet_id))
        self.assertEqual(200, response.status_code)
        self.assertEqual('image/svg+xml', response.mimetype)
        self.assertIn(b'COBS', response.data)

    def test_comet_light_curve_image_without_magnitude_params(self):
        comet = self._create_comet(magnitude_g=None, magnitude_k=None)
        response = self.client.get('/comet/{}/light-curve-img'.format(comet.comet_id))
        self.assertEqual(404, response.status_code)

    def test_minor_planet_light_curve_page_and_image(self):
        minor_planet = MinorPlanet(int_designation=4, designation='(4) Vesta', magnitude_H=3.25, magnitude_G=0.32)
        db.session.add(minor_planet)
        db.session.commit()
        mpc_row = pd.Series({
            'designation': '(4) Vesta', 'epoch_packed': 'K25BL', 'semimajor_axis_au': 2.3615,
            'eccentricity': 0.0902, 'inclination_degrees': 7.144, 'longitude_of_ascending_node_degrees': 103.70,
            'argument_of_perihelion_degrees': 151.54, 'mean_anomaly_degrees': 26.8,
        })

        response = self.client.get('/minor-planet/4/light-curve')
        self.assertEqual(200, response.status_code)
        self.assertIn(b'light-curve-img', response.data)

        with patch('app.main.solarsystem.minor_planet_views.find_mpc_minor_planet', return_value=mpc_row):
            response = self.client.get('/minor-planet/4/light-curve-img?range=730')
        self.assertEqual(200, response.status_code)
        self.assertEqual('image/svg+xml', response.mimetype)

    def test_minor_planet_light_curve_without_absolute_magnitude(self):
        db.session.add(MinorPlanet(int_designation=99999, designation='Unknown'))
        db.session.commit()
        response = self.client.get('/minor-planet/99999/light-curve')
        self.assertEqual(200, response.status_code)
        self.assertNotIn(b'light-curve-img', response.data)
        self.assertEqual(404, self.client.get('/minor-planet/99999/light-curve-img').status_code)


if __name__ == '__main__':
    unittest.main()
