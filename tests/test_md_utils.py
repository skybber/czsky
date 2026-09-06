import unittest
from unittest.mock import patch

from app import create_app
from app.commons.md_utils import parse_extended_commonmark
from app.models import DeepskyObject


class MarkdownDsoLinksTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def _render_dso_link(self, embed=None, ext_url_params='', request_path='/'):
        dso = DeepskyObject(id=42, name='NGC1')
        with self.app.test_request_context(request_path), patch(
            'app.commons.md_utils.normalize_dso_name', return_value='NGC1'
        ), patch('app.commons.md_utils.DeepskyObject.query') as query:
            query.filter_by.return_value.first.return_value = dso
            return parse_extended_commonmark(
                'See NGC 1.', '', ext_url_params, embed=embed
            )

    def test_standalone_dso_link_targets_selected_tab(self):
        rendered = self._render_dso_link()

        self.assertIn('href="/deepskyobject/NGC1/seltab"', rendered)
        self.assertNotIn('data-embed-map-url', rendered)

    def test_chart_embedded_dso_link_selects_object_on_map(self):
        rendered = self._render_dso_link(
            embed='fc', request_path='/?embed=fc'
        )

        self.assertIn('href="/deepskyobject/NGC1/info?embed=fc"', rendered)
        self.assertIn(
            'data-embed-map-url="/deepskyobject/NGC1/chart?splitview=true"',
            rendered,
        )

    def test_chart_embedded_map_url_preserves_session_plan_context(self):
        rendered = self._render_dso_link(
            embed='fc',
            request_path=(
                '/?embed=fc&back=session_plan&back_id=7&season=winter'
            ),
        )

        self.assertIn('/session-plan/7/chart?', rendered)
        self.assertIn('obj_id=dso42', rendered)
        self.assertIn('back=session_plan', rendered)
        self.assertIn('back_id=7', rendered)
        self.assertIn('season=winter', rendered)
        self.assertIn('splitview=true', rendered)

    def test_external_url_parameters_are_appended_after_embed(self):
        rendered = self._render_dso_link(
            embed='pl', ext_url_params='?back=constell&back_id=Ori'
        )

        self.assertIn(
            'href="/deepskyobject/NGC1/info?embed=pl&back=constell&back_id=Ori"',
            rendered,
        )
        self.assertNotIn('data-embed-map-url', rendered)


if __name__ == '__main__':
    unittest.main()
