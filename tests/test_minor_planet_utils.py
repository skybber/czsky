import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import create_app, db
from app.commons import minor_planet_utils
from app.models import MinorPlanet

CERES_LINE = ('00001    3.33  0.15 K243V 102.95073   73.36090   80.25353   10.58759  0.0790274  0.21412733'
              '   2.7670775  0 E2024-MB4  7314 125 1801-2024 0.80 M-v 30k MPCLINUX   4000      (1) Ceres'
              '              20240628\n')
PALLAS_LINE = ('00002    4.10  0.15 K243V  83.32723  310.88726  172.91472   34.92284  0.2303399  0.21373952'
               '   2.7704235  0 E2024-N27  8953 123 1804-2024 0.75 M-c 28k MPCLINUX   4000      (2) Pallas'
               '             20240701\n')


class MinorPlanetUtilsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.excerpt_file = os.path.join(self.tmp_dir.name, 'MPCORB.9999.DAT')
        self._write_excerpt(CERES_LINE)
        self.excerpt_patch = patch.object(minor_planet_utils, 'MPCORB_EXCERPT_FILE', self.excerpt_file)
        self.excerpt_patch.start()
        minor_planet_utils.reset_minor_planets_cache()

    def tearDown(self):
        self.excerpt_patch.stop()
        minor_planet_utils.reset_minor_planets_cache()
        self.tmp_dir.cleanup()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _write_excerpt(self, *lines):
        with open(self.excerpt_file, 'w', encoding='ascii') as f:
            f.writelines(lines)

    def test_elements_reload_after_file_is_appended_by_another_process(self):
        self.assertEqual(len(minor_planet_utils.get_all_mpc_minor_planets()), 1)
        with self.assertRaises(KeyError):
            minor_planet_utils.find_mpc_minor_planet('00002')

        with open(self.excerpt_file, 'a', encoding='ascii') as f:
            f.write(PALLAS_LINE)

        self.assertEqual(len(minor_planet_utils.get_all_mpc_minor_planets()), 2)
        self.assertEqual(minor_planet_utils.find_mpc_minor_planet('00002')['designation'], '(2) Pallas')

    def test_elements_reload_after_file_is_replaced(self):
        self.assertEqual(minor_planet_utils.find_mpc_minor_planet('00001')['magnitude_H'], 3.33)

        replaced_file = self.excerpt_file + '.tmp'
        with open(replaced_file, 'w', encoding='ascii') as f:
            f.write(CERES_LINE.replace('    3.33  ', '    3.40  ', 1))
        os.replace(replaced_file, self.excerpt_file)

        self.assertEqual(minor_planet_utils.find_mpc_minor_planet('00001')['magnitude_H'], 3.40)

    def test_position_cache_is_cleared_when_file_changes(self):
        dt = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
        minor_planet_utils.get_minor_planet_radec('00001', dt)
        self.assertEqual(minor_planet_utils._get_minor_planet_cached.cache_info().currsize, 1)

        with open(self.excerpt_file, 'a', encoding='ascii') as f:
            f.write(PALLAS_LINE)
        minor_planet_utils.get_all_mpc_minor_planets()

        self.assertEqual(minor_planet_utils._get_minor_planet_cached.cache_info().currsize, 0)

    def test_cached_position_is_recomputed_after_file_change(self):
        dt = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
        old_ra, old_dec = minor_planet_utils.get_minor_planet_radec('00001', dt)

        # Shift the mean anomaly so Ceres lands elsewhere; same length keeps the columns.
        replaced_file = self.excerpt_file + '.tmp'
        with open(replaced_file, 'w', encoding='ascii') as f:
            f.write(CERES_LINE.replace(' 102.95073 ', ' 112.95073 ', 1))
        os.replace(replaced_file, self.excerpt_file)

        new_ra, new_dec = minor_planet_utils.get_minor_planet_radec('00001', dt)
        self.assertNotAlmostEqual(old_ra, new_ra, places=4)

    def test_rebuild_excerpt_publishes_complete_file_at_once(self):
        header = ['header\n'] * (minor_planet_utils.MPCORB_EXCERPT_FIRST_ROW - 1)
        base_rows = [CERES_LINE] * (minor_planet_utils.MPCORB_EXCERPT_LAST_ROW
                                    - minor_planet_utils.MPCORB_EXCERPT_FIRST_ROW + 1)
        extra_row = PALLAS_LINE.replace('00002', 'K26U00K', 1)
        mpcorb_file = os.path.join(self.tmp_dir.name, 'MPCORB.DAT')
        with open(mpcorb_file, 'w', encoding='ascii') as f:
            f.writelines(header + base_rows + [PALLAS_LINE, extra_row])

        published_sizes = []
        real_replace = os.replace

        def recording_replace(src, dst):
            published_sizes.append(os.path.getsize(src))
            real_replace(src, dst)

        with patch.object(minor_planet_utils.os, 'replace', side_effect=recording_replace):
            not_found = minor_planet_utils.rebuild_mpcorb_excerpt(mpcorb_file, ['K26U00K', 'K99Z99Z'])

        with open(self.excerpt_file, encoding='ascii') as f:
            lines = f.readlines()
        self.assertEqual(len(published_sizes), 1)
        self.assertEqual(published_sizes[0], os.path.getsize(self.excerpt_file))
        self.assertEqual(len(lines), len(base_rows) + 1)
        self.assertEqual(lines[-1][:7].strip(), 'K26U00K')
        self.assertEqual(not_found, {'K99Z99Z'})
        self.assertEqual([n for n in os.listdir(self.tmp_dir.name) if n.endswith('.tmp')], [])

    def test_unchanged_file_is_not_reloaded(self):
        first = minor_planet_utils.get_all_mpc_minor_planets()
        self.assertIs(minor_planet_utils.get_all_mpc_minor_planets(), first)

    def test_update_elements_refreshes_stale_db_rows_and_skips_missing(self):
        ceres = MinorPlanet(int_designation=1, mpc_designation='00001', designation='(1) Ceres',
                            magnitude_H=9.99, magnitude_G=0.5, semimajor_axis_au=1.0)
        missing = MinorPlanet(int_designation=99999, mpc_designation='99999', magnitude_H=12.0)
        db.session.add_all([ceres, missing])
        db.session.commit()

        # Load the elements first; the update itself must not touch Skyfield ephemerides.
        minor_planet_utils.get_all_mpc_minor_planets()
        with patch.object(minor_planet_utils, 'load') as skyfield_load:
            minor_planet_utils.update_minor_planets_elements_from_mpc()
        skyfield_load.assert_not_called()

        ceres = MinorPlanet.query.filter_by(mpc_designation='00001').one()
        self.assertEqual(ceres.magnitude_H, 3.33)
        self.assertEqual(ceres.magnitude_G, 0.15)
        self.assertAlmostEqual(ceres.semimajor_axis_au, 2.7670775)
        self.assertIsNone(ceres.cur_ra)

        missing = MinorPlanet.query.filter_by(mpc_designation='99999').one()
        self.assertEqual(missing.magnitude_H, 12.0)


if __name__ == '__main__':
    unittest.main()
