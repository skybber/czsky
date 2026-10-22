import csv
import math
import os
import tempfile
import unittest

from fchart3.deepsky_object import DsoType
from fchart3.hnsky_deepsky import import_hnsky_supplement as fchart3_import_hnsky_supplement

from app import create_app, db
from app.commons.dso_utils import denormalize_dso_name, split_catalog_name
from app.commons.search_sky_object_utils import search_dso_by_position
from app.models import DeepskyObject
from imports import make_bright_quasars as mbq

SUPPLEMENT_FILE = 'data/supplements/Bright quasars, Veron-Cetty & Veron 13th.sup'
DSO_LIST_FILE = 'data/dsolist/BrightQuasars.csv'


def _obj(vcv_name, ra, dec, vmag=15.0, z=1.0, cl='Q'):
    return {'vcv_name': vcv_name, 'ra': ra, 'dec': dec, 'vmag': vmag, 'z': z, 'cl': cl, 'sp': ''}


class MakeBrightQuasarsTestCase(unittest.TestCase):
    def test_czsky_qso_name_keeps_leading_zeros_and_sign(self):
        self.assertEqual(mbq.czsky_qso_name('00 17 08.1', '+81 35 07'), 'QSO0017+8135')
        self.assertEqual(mbq.czsky_qso_name('21 58 52.0', '-30 13 32'), 'QSO2158-3013')

    def test_vcv_name_to_common_name(self):
        self.assertEqual(mbq.vcv_name_to_common_name('3C 273.0'), '3C 273')
        self.assertEqual(mbq.vcv_name_to_common_name('3C 249.1'), '3C 249.1')
        self.assertEqual(mbq.vcv_name_to_common_name('MARK 421'), 'Mrk 421')

    def test_lookback_time(self):
        # 3C 273: ~2.0 Gyr, APM 08279+5255: ~12.2 Gyr for Planck 2018
        self.assertAlmostEqual(mbq.lookback_time_gyr(0.158), 2.04, delta=0.03)
        self.assertAlmostEqual(mbq.lookback_time_gyr(3.911), 12.22, delta=0.05)

    def test_assign_names_suffix_for_close_pair_and_existing_dso(self):
        objects = [
            _obj('Q 0957+561B', '10 01 20.9', '+55 53 49'),
            _obj('Q 0957+561A', '10 01 20.8', '+55 53 54'),
            _obj('3C 273.0', '12 29 06.7', '+02 03 08'),
        ]
        mbq._assign_names(objects)
        self.assertEqual([o['dso_name'] for o in objects], ['QSO1001+5553B', 'QSO1001+5553A', 'PGC41121'])
        self.assertEqual([o['is_new'] for o in objects], [True, True, False])

    def test_written_supplement_is_readable_by_fchart3(self):
        objects = [
            _obj('PKS 2155-304', '21 58 52.0', '-30 13 32', vmag=13.09, cl='B'),
            _obj('3C 273.0', '12 29 06.7', '+02 03 08', vmag=12.85),
        ]
        mbq._assign_names(objects)
        with tempfile.TemporaryDirectory() as tmp_dir:
            sup_file = os.path.join(tmp_dir, 'test.sup')
            mbq._write_supplement(objects, sup_file)
            all_dsos = {}
            dsos = fchart3_import_hnsky_supplement(sup_file, all_dsos)

        self.assertEqual(len(dsos), 1)  # existing 3C 273 is not written
        dso = dsos[0]
        self.assertEqual((dso.cat, dso.name), ('QSO', '2158-3013'))
        self.assertEqual(dso.type, DsoType.QSO)
        self.assertAlmostEqual(dso.mag, 13.09, places=2)
        self.assertAlmostEqual(math.degrees(dso.dec), -30.22556, places=4)
        self.assertAlmostEqual(math.degrees(dso.ra) / 15.0, 21.981111, places=5)


class BrightQuasarsDataTestCase(unittest.TestCase):
    def test_dso_list_names_are_in_supplement_or_existing(self):
        all_dsos = {}
        fchart3_import_hnsky_supplement(SUPPLEMENT_FILE, all_dsos)
        existing = set(mbq.EXISTING_DSOS.values())
        with open(DSO_LIST_FILE) as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        self.assertGreater(len(rows), 0)
        names = [r['DSO_NAME'] for r in rows]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(name in all_dsos or name in existing, name)

    def test_supplement_objects_are_quasars(self):
        dsos = fchart3_import_hnsky_supplement(SUPPLEMENT_FILE, {})
        self.assertTrue(all(d.type == DsoType.QSO and d.cat == 'QSO' for d in dsos))


class QsoNameTestCase(unittest.TestCase):
    def test_qso_name_is_not_unzeroed(self):
        self.assertEqual(denormalize_dso_name('QSO0017+8135'), 'QSO 0017+8135')
        self.assertEqual(split_catalog_name('QSO1001+5553A'), ('QSO', '1001+5553A'))


class SearchDsoByPositionTestCase(unittest.TestCase):
    ARCSEC = math.radians(1.0 / 3600.0)

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _add(self, name, ra, dec, dso_type='QSO'):
        dso = DeepskyObject(name=name, type=dso_type, ra=ra, dec=dec, mag=15.0)
        db.session.add(dso)
        db.session.commit()
        return dso

    def test_returns_nearest_within_radius(self):
        self._add('QSO_NEAR', 1.0 + 6 * self.ARCSEC / math.cos(0.5), 0.5)
        nearer = self._add('QSO_NEARER', 1.0, 0.5 + 2 * self.ARCSEC)
        self.assertEqual(search_dso_by_position(1.0, 0.5, 'QSO').name, nearer.name)

    def test_ignores_objects_outside_radius_and_other_types(self):
        self._add('QSO_FAR', 1.0, 0.5 + 20 * self.ARCSEC)
        self._add('GX_NEAR', 1.0, 0.5, dso_type='GX')
        self.assertIsNone(search_dso_by_position(1.0, 0.5, 'QSO'))

    def test_matches_across_ra_zero(self):
        ra_near_360 = 2.0 * math.pi - math.radians(0.001)
        ra_near_0 = math.radians(0.001)
        self._add('QSO_RA360', ra_near_360, 0.0)
        self.assertEqual(search_dso_by_position(ra_near_0, 0.0, 'QSO').name, 'QSO_RA360')
        db.session.query(DeepskyObject).delete()
        self._add('QSO_RA0', ra_near_0, 0.0)
        self.assertEqual(search_dso_by_position(ra_near_360, 0.0, 'QSO').name, 'QSO_RA0')

    def test_matches_near_pole(self):
        self._add('QSO_POLE', 3.0, math.radians(90.0) - 3 * self.ARCSEC)
        self.assertEqual(search_dso_by_position(0.0, math.radians(90.0) - 3 * self.ARCSEC, 'QSO').name, 'QSO_POLE')

    def test_returns_none_without_type(self):
        self.assertIsNone(search_dso_by_position(1.0, 0.5, None))


if __name__ == '__main__':
    unittest.main()
