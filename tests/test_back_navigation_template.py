import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class BackNavigationTemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template_dir = Path(__file__).resolve().parents[1] / 'app' / 'templates'
        cls.environment = Environment(loader=FileSystemLoader(template_dir))
        cls.environment.globals['url_for'] = cls._url_for

    @staticmethod
    def _url_for(endpoint, **kwargs):
        return '/' + endpoint

    def _render_navigation(self, embed):
        template = self.environment.from_string(
            "{% import 'macros/back_navig_macros.html' as back_navig %}"
            "{{ back_navig.back_navig(None, None, 'deepskyobjects', embed) }}"
        )
        return template.render(embed=embed)

    def test_back_navigation_is_hidden_in_embedded_detail(self):
        for embed in ('fc', 'pl', 'planets'):
            with self.subTest(embed=embed):
                self.assertEqual('', self._render_navigation(embed).strip())

    def test_back_navigation_is_shown_in_standalone_detail(self):
        rendered = self._render_navigation(None)

        self.assertIn('ui basic icon compact button', rendered)
        self.assertIn('main_deepskyobject.deepskyobjects', rendered)
        self.assertIn('<div class="divider"></div>', rendered)


if __name__ == '__main__':
    unittest.main()
