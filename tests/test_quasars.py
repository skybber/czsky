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
from imports import make_quasars as mq

SUPPLEMENT_FILE = mq.SUPPLEMENT_FILE
QUASARS_DATA_FILE = mq.QUASARS_DATA_FILE
DSO_LIST_FILE = mq.DSO_LIST_FILE


def _obj(cat_name, ra, dec, vmag=15.0, z=1.0, bllac=False, source='VCV13'):
    return {'cat_name': cat_name, 'common_name': cat_name, 'ra': ra, 'dec': dec, 'vmag': vmag, 'z': z,
            'bllac': bllac, 'source': source}


def _deg(ra, dec):
    return mq.sexagesimal_to_float(ra) * 15.0, mq.sexagesimal_to_float(dec)


class MakeQuasarsTestCase(unittest.TestCase):
    def test_czsky_qso_name_keeps_leading_zeros_and_sign(self):
        self.assertEqual(mq.czsky_qso_name(*_deg('00 17 08.1', '+81 35 07')), 'QSO0017+8135')
        self.assertEqual(mq.czsky_qso_name(*_deg('21 58 52.0', '-30 13 32')), 'QSO2158-3013')
        self.assertEqual(mq.czsky_qso_name(*_deg('12 00 00.0', '-00 30 00')), 'QSO1200-0030')
        self.assertEqual(mq.czsky_qso_name(359.9999, 0.0), 'QSO2359+0000')

    def test_catalog_name_to_common_name(self):
        self.assertEqual(mq.catalog_name_to_common_name('3C  273.0'), '3C 273')
        self.assertEqual(mq.catalog_name_to_common_name('3C 249.1'), '3C 249.1')
        self.assertEqual(mq.catalog_name_to_common_name('MARK 421'), 'Mrk 421')

    def test_milliquas_vmag(self):
        self.assertAlmostEqual(mq.milliquas_vmag(17.0, 18.0), 17.5)
        self.assertAlmostEqual(mq.milliquas_vmag(18.0, 17.0), 17.5)
        # color limited to MAX_COLOR_BR, the fainter magnitude is preferred
        self.assertAlmostEqual(mq.milliquas_vmag(11.36, 18.01), 18.01 - mq.MAX_COLOR_BR / 2.0)
        self.assertEqual(mq.milliquas_vmag(17.0, None), 17.0)
        self.assertIsNone(mq.milliquas_vmag(None, None))

    def test_absolute_mag(self):
        # 3C 273 M_V ~ -26.6, Ton 618 ~ -30.4
        self.assertAlmostEqual(mq.absolute_mag(12.85, 0.158), -26.6, delta=0.1)
        self.assertAlmostEqual(mq.absolute_mag(15.87, 2.219), -30.4, delta=0.1)
        self.assertGreater(mq.absolute_mag(15.87, 2.219), mq.MIN_ABS_MAG)

    def test_extent_index(self):
        index = mq.ExtentIndex()
        index.add(80.0, -69.0, 3600.0, 'LMC')
        self.assertEqual(index.containing(80.5, -69.5), 'LMC')
        self.assertIsNone(index.containing(80.0, -67.9))

    def test_lookback_time(self):
        # 3C 273: ~2.0 Gyr, APM 08279+5255: ~12.2 Gyr for Planck 2018
        self.assertAlmostEqual(mq.lookback_time_gyr(0.158), 2.04, delta=0.03)
        self.assertAlmostEqual(mq.lookback_time_gyr(3.911), 12.22, delta=0.05)

    def test_position_index_across_ra_zero(self):
        index = mq.PositionIndex()
        index.add(359.9995, 10.0, 'a')
        self.assertEqual(index.nearest(0.0005, 10.0, 5.0), 'a')
        self.assertIsNone(index.nearest(0.01, 10.0, 5.0))

    def test_assign_names_suffix_for_close_pair_and_existing_dso(self):
        objects = [
            _obj('Q 0957+561B', *_deg('10 01 20.9', '+55 53 49')),
            _obj('Q 0957+561A', *_deg('10 01 20.8', '+55 53 54')),
            _obj('3C 273.0', *_deg('12 29 06.7', '+02 03 08')),
            # Milliquas object of the same name as existing DSO in VCV is not existing
            _obj('3C 273.0', *_deg('12 29 06.7', '+02 03 08'), source='MQ8'),
        ]
        mq.assign_names(objects)
        self.assertEqual([o['dso_name'] for o in objects],
                         ['QSO1001+5553B', 'QSO1001+5553A', 'PGC41121', 'QSO1229+0203'])
        self.assertEqual([o['is_new'] for o in objects], [True, True, False, True])

    def test_select_milliquas_objects(self):
        list_objects = [_obj('PKS 2155-304', 329.7167, -30.2256)]
        existing = mq.PositionIndex()
        existing.add(150.0, 20.0, 'PGC1')
        galaxies = mq.ExtentIndex()
        galaxies.add(80.0, -69.0, 3600.0, 'LMC')
        milliquas = [
            _obj('PKS 2155-304', 329.7168, -30.2257, source='MQ8'),     # in DSO list
            _obj('UM 1', 150.0005, 20.0, source='MQ8'),                 # existing DSO
            _obj('UM 2', 151.0, 20.0, source='MQ8'),
            _obj('LMC nucleus', 80.1, -69.1, z=0.05, source='MQ8'),     # low z inside galaxy
            _obj('MQS behind LMC', 80.2, -69.2, z=1.0, source='MQ8'),   # background quasar
            _obj('DESI bogus', 152.0, 20.0, vmag=10.45, z=1.075, source='MQ8'),
            _obj('No z', 153.0, 20.0, z=None, source='MQ8'),
        ]
        selected = mq.select_milliquas_objects(milliquas, list_objects, existing, galaxies)
        self.assertEqual([o['cat_name'] for o in selected], ['UM 2', 'MQS behind LMC', 'No z'])

    def test_written_files_are_consistent_and_readable_by_fchart3(self):
        objects = [
            _obj('PKS 2155-304', *_deg('21 58 52.0', '-30 13 32'), vmag=13.09, z=0.116, bllac=True),
            _obj('3C 273.0', *_deg('12 29 06.7', '+02 03 08'), vmag=12.85),
            _obj('SDSS J1', 10.0, -0.5, vmag=17.2, z=None, source='MQ8'),
        ]
        mq.assign_names(objects)
        with tempfile.TemporaryDirectory() as tmp_dir:
            sup_file = os.path.join(tmp_dir, 'test.sup')
            data_file = os.path.join(tmp_dir, 'test.csv')
            self.assertEqual(mq.write_supplement(objects, sup_file), 2)  # existing 3C 273 is not written
            mq.write_quasars_data(objects, data_file)
            dsos = fchart3_import_hnsky_supplement(sup_file, {})
            with open(data_file) as f:
                rows = list(csv.DictReader(f, delimiter=';'))

        by_name = {d.cat + d.name: d for d in dsos}
        self.assertEqual(set(by_name), {'QSO2158-3013', 'QSO0040-0030'})
        pks = by_name['QSO2158-3013']
        self.assertEqual(pks.type, DsoType.QSO)
        self.assertAlmostEqual(pks.mag, 13.09, places=2)
        self.assertAlmostEqual(math.degrees(pks.dec), -30.22556, places=4)
        self.assertAlmostEqual(math.degrees(pks.ra) / 15.0, 21.981111, places=5)
        self.assertAlmostEqual(math.degrees(by_name['QSO0040-0030'].dec), -0.5, places=4)

        self.assertEqual([r['DSO_NAME'] for r in rows], ['QSO0040-0030', 'QSO2158-3013'])
        self.assertEqual(rows[0]['Z'], '')
        self.assertEqual(rows[0]['DIST'], '')
        self.assertAlmostEqual(float(rows[1]['DIST']), 1.54e9, delta=0.02e9)


class QuasarsDataTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supplement_dsos = {}
        fchart3_import_hnsky_supplement(SUPPLEMENT_FILE, cls.supplement_dsos)

    def test_supplement_objects_are_unique_quasars(self):
        dsos = fchart3_import_hnsky_supplement(SUPPLEMENT_FILE, {})
        self.assertTrue(all(d.type == DsoType.QSO and d.cat == 'QSO' for d in dsos))
        self.assertEqual(len(dsos), len(self.supplement_dsos))

    def test_quasars_data_match_supplement(self):
        with open(QUASARS_DATA_FILE, encoding='utf-8') as f:
            names = [r['DSO_NAME'] for r in csv.DictReader(f, delimiter=';')]
        self.assertEqual(sorted(names), sorted(self.supplement_dsos))

    def test_dso_list_names_are_in_supplement_or_existing(self):
        existing = set(mq.EXISTING_DSOS.values())
        with open(DSO_LIST_FILE, encoding='utf-8') as f:
            names = [r['DSO_NAME'] for r in csv.DictReader(f, delimiter=';')]
        self.assertGreater(len(names), 0)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertTrue(name in self.supplement_dsos or name in existing, name)


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
