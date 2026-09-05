import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app, db
from app.commons.comet_utils import find_comet_by_cobs_name, update_comets_cobs_observations
from app.models import Comet, CometObservation


class CometUtilsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _add_comet(self, designation, comet_id=None, eval_mag=12.0):
        comet = Comet(
            comet_id=comet_id or designation.replace('/', '').replace(' ', ''),
            designation=designation,
            eval_mag=eval_mag,
            mag=eval_mag,
        )
        db.session.add(comet)
        db.session.commit()
        return comet

    def test_find_comet_by_cobs_name_matches_legacy_numbered_suffix(self):
        comet = self._add_comet('10P/Tempel')

        found = find_comet_by_cobs_name('10P/Tempel 2')

        self.assertEqual(found.id, comet.id)

    def test_find_comet_by_cobs_name_preserves_existing_prefix_match(self):
        comet = self._add_comet('C/2025 X1 (Example)')

        found = find_comet_by_cobs_name('C/2025 X1')

        self.assertEqual(found.id, comet.id)

    def test_find_comet_by_cobs_name_returns_none_for_unmatched_name(self):
        self._add_comet('10P/Tempel')

        found = find_comet_by_cobs_name('99P/Unknown')

        self.assertIsNone(found)

    def test_update_comets_cobs_observations_imports_legacy_numbered_suffix(self):
        comet = self._add_comet('10P/Tempel', comet_id='0010P', eval_mag=14.0)
        html = b'''
            <html>
              <body>
                <p class="text-info">
                  <strong><a>10P/Tempel 2</a></strong>
                  <strong>2026</strong>
                  <code>Jul 2.5, 9.8, 3' (Observer; note)</code>
                </p>
              </body>
            </html>
        '''

        with patch('app.commons.comet_utils.requests.get', return_value=SimpleNamespace(content=html)):
            update_comets_cobs_observations()

        observations = CometObservation.query.filter_by(comet_id=comet.id).all()
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].mag, 9.8)
        self.assertEqual(observations[0].coma_diameter, 3.0)


if __name__ == '__main__':
    unittest.main()
