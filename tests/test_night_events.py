import unittest
from datetime import datetime, timezone

from app import create_app
from app.commons.night_events import night_info


class NightEventsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_prague_autumn_night(self):
        # Local noon CEST of 2026-10-16
        info = night_info(50.08, 14.42, datetime(2026, 10, 16, 10, 0, tzinfo=timezone.utc))
        self.assertTrue(info['sun']['set'].startswith('2026-10-16T16:0'))
        self.assertTrue(info['sun']['rise'].startswith('2026-10-17T05:2'))
        night = info['astronomicalNight']
        self.assertTrue(info['sun']['set'] < night['from'] < night['to'] < info['sun']['rise'])
        self.assertIn(info['moon']['phaseName'], ('waxing_crescent', 'first_quarter'))
        self.assertTrue(0.0 <= info['moon']['illumination'] <= 1.0)

    def test_no_astronomical_night_in_summer_north(self):
        info = night_info(55.6, 12.6, datetime(2026, 6, 21, 10, 0, tzinfo=timezone.utc))
        self.assertIsNone(info['astronomicalNight']['from'])
        self.assertIsNotNone(info['sun']['set'])

    def test_polar_day_and_night(self):
        summer = night_info(78.0, 15.0, datetime(2026, 6, 21, 10, 0, tzinfo=timezone.utc))
        self.assertTrue(summer['sun']['upAllNight'])
        winter = night_info(78.0, 15.0, datetime(2026, 12, 21, 11, 0, tzinfo=timezone.utc))
        self.assertTrue(winter['sun']['downAllNight'])

    def test_endpoint(self):
        response = self.client.get('/chart/night-info?lat=50.08&lon=14.42&start=2026-10-16T10:00:00.000Z')
        self.assertEqual(200, response.status_code)
        self.assertEqual('2026-10-16T10:00:00Z', response.json['nightStart'])
        self.assertIn('moon', response.json)

    def test_endpoint_rejects_invalid_input(self):
        self.assertEqual(400, self.client.get('/chart/night-info?lat=x&lon=1&start=2026-10-16T10:00:00Z').status_code)
        self.assertEqual(400, self.client.get('/chart/night-info?lat=95&lon=1&start=2026-10-16T10:00:00Z').status_code)
        self.assertEqual(400, self.client.get('/chart/night-info?lat=50&lon=14').status_code)


if __name__ == '__main__':
    unittest.main()
