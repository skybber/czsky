import unittest

from app import create_app, db
from app.commons.search_sky_object_utils import search_dso, search_dso_by_common_name
from app.models import DeepskyObject


class SearchDsoTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _add(self, name, common_name=None, master=None):
        dso = DeepskyObject(name=name, type='QSO', ra=1.0, dec=0.5, mag=15.0, common_name=common_name,
                            master_id=master.id if master else None)
        db.session.add(dso)
        db.session.commit()
        return dso

    def test_finds_by_name(self):
        self._add('QSO1228+3128', 'Ton 618')
        self.assertEqual(search_dso('QSO1228+3128').name, 'QSO1228+3128')
        self.assertEqual(search_dso('QSO 1228+3128').name, 'QSO1228+3128')

    def test_finds_by_common_name_ignoring_case_and_spaces(self):
        self._add('QSO1228+3128', 'Ton 618')
        self._add('QSO2158-3013', 'PKS 2155-304')
        self.assertEqual(search_dso('Ton 618').name, 'QSO1228+3128')
        self.assertEqual(search_dso('ton618').name, 'QSO1228+3128')
        self.assertEqual(search_dso('PKS2155-304').name, 'QSO2158-3013')
        self.assertEqual(search_dso('PKS%202155-304').name, 'QSO2158-3013')

    def test_name_has_priority_over_common_name(self):
        self._add('NGC7000', 'North America Nebula')
        self._add('QSO0000+0000', 'NGC 7000')
        self.assertEqual(search_dso('NGC 7000').name, 'NGC7000')

    def test_prefers_master_object(self):
        master = self._add('PGC41121', '3C 273')
        self._add('QSO1229+0203', '3C 273', master=master)
        self.assertEqual(search_dso_by_common_name('3C 273').name, 'PGC41121')

    def test_does_not_match_short_or_numeric_queries(self):
        self._add('QSO0000+0000', '31')
        self._add('QSO0000+0001', 'AB')
        self.assertIsNone(search_dso('31'))
        self.assertIsNone(search_dso('AB'))
        self.assertIsNone(search_dso('Unknown object'))


if __name__ == '__main__':
    unittest.main()
