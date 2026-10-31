import unittest

from app import create_app


class ConvertMagMacroTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.macros = self.app.jinja_env.get_template('macros/common_macros.html').module

    def tearDown(self):
        self.app_context.pop()

    def test_float_noise_is_rounded(self):
        # float division in supplement import, float32 values from Simbad
        self.assertEqual(str(self.macros.convert_mag(15.430000000000001)), '15.43')
        self.assertEqual(str(self.macros.convert_mag(18.270000457763672)), '18.27')

    def test_regular_and_missing_values(self):
        self.assertEqual(str(self.macros.convert_mag(15.4)), '15.4')
        self.assertEqual(str(self.macros.convert_mag(100.0)), '- ')
        self.assertEqual(str(self.macros.convert_mag(None)), '- ')


if __name__ == '__main__':
    unittest.main()
