import unittest

from imports.import_hnsky import fix_hnsky_decimal_commas


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
