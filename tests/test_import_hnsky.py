import unittest

from imports.import_hnsky import fix_hnsky_decimal_commas, read_hnsky_name_groups, is_stale_hnsky_master_link


class StaleHnskyMastersTestCase(unittest.TestCase):
    LINES = [
        '154200,199043,799,B8/LDN1394   ,DN[5];Grouping_of_LDN_1392;B8;B9,799,260,260\n',
        '155000,198784,799,B9/MLB71/LDN1400H   ,DN,799,70,70\n',
        '100,200,120,NGC123A/UGC5,GX,1,2,3\n',
    ]

    def setUp(self):
        self.groups = read_hnsky_name_groups(self.LINES)

    def test_names_from_comment_are_ignored(self):
        self.assertEqual(self.groups['B8'], self.groups['LDN1394'])
        self.assertNotEqual(self.groups['B8'], self.groups['B9'])

    def test_stale_link_on_different_lines(self):
        self.assertTrue(is_stale_hnsky_master_link('B9', 'B8', self.groups))

    def test_valid_link_on_same_line(self):
        self.assertFalse(is_stale_hnsky_master_link('LDN1394', 'B8', self.groups))
        self.assertFalse(is_stale_hnsky_master_link('LDN1400H', 'B9', self.groups))

    def test_derived_fake_master(self):
        self.assertFalse(is_stale_hnsky_master_link('NGC123A', 'NGC123', self.groups))
        self.assertFalse(is_stale_hnsky_master_link('UGC5', 'NGC123', self.groups))

    def test_ngc_subcomponent_link(self):
        self.assertFalse(is_stale_hnsky_master_link('NGC777_2', 'NGC777', self.groups))

    def test_missing_name_is_undecided(self):
        self.assertIsNone(is_stale_hnsky_master_link('LDN1392', 'B8', self.groups))


class FixHnskyDecimalCommasTestCase(unittest.TestCase):
    def test_pgc_line_with_split_brightness(self):
        items = '45656,-54,153,PGC4591/UGC821,GX/[Sb],141,89,10,3,70'.split(',')
        self.assertEqual(fix_hnsky_decimal_commas(items)[5:],
                         ['141.89', '10', '3', '70'])

    def test_pk_line_with_split_dimensions(self):
        items = '644630,100798,120,PK_053+24.1/PN_Vy1-2/PNG053.3+24.0,PN,61,0,9,0,7'.split(',')
        self.assertEqual(fix_hnsky_decimal_commas(items)[5:],
                         ['61', '0.9', '0.7'])

    def test_regular_line_unchanged(self):
        items = '48791,44682,141,PGC4913/UGC891,GX/[S(B)+],156,27,13,49'.split(',')
        self.assertIs(fix_hnsky_decimal_commas(items), items)

    def test_other_10_items_line_unchanged(self):
        items = '705789,106370,117,M1-92,BN/[R],73,3,2,0,130'.split(',')
        self.assertIs(fix_hnsky_decimal_commas(items), items)


if __name__ == '__main__':
    unittest.main()
