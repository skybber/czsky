import io
from pathlib import Path
import tempfile
import unittest

from app.commons import openastronomylog as oal


class OpenAstronomyLogSecurityTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.marker = Path(directory.name) / 'marker.txt'
        self.marker.write_text('OAL_PRIVATE_FILE_MARKER', encoding='utf-8')

    def _document(self, name, doctype=''):
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'{doctype}'
            '<observations><sites><site id="test-site">'
            f'<name>{name}</name>'
            '<longitude unit="deg">14.5</longitude>'
            '<latitude unit="deg">50.0</latitude>'
            '</site></sites></observations>'
        ).encode('utf-8')

    def _external_entity_document(self):
        return self._document(
            '&private;',
            '<!DOCTYPE observations ['
            f'<!ENTITY private SYSTEM "{self.marker.as_uri()}">]>',
        )

    def test_xml_helpers_do_not_expand_external_file_entities(self):
        xml = self._external_entity_document()
        for source in ('file', 'string'):
            with self.subTest(source=source):
                if source == 'file':
                    root = oal.parsexml_(io.BytesIO(xml)).getroot()
                else:
                    root = oal.parsexmlstring_(xml)
                self.assertNotIn('OAL_PRIVATE_FILE_MARKER', ''.join(root.itertext()))

    def test_oal_import_does_not_read_external_file_into_location(self):
        observations = oal.parse(
            io.BytesIO(self._external_entity_document()), silence=True,
        )
        site = observations.get_sites().get_site()[0]
        self.assertNotIn('OAL_PRIVATE_FILE_MARKER', site.get_name() or '')

    def test_xml_helpers_do_not_expand_custom_internal_entities(self):
        xml = self._document(
            '&custom;',
            '<!DOCTYPE observations [<!ENTITY custom "EXPANDED_ENTITY_MARKER">]>',
        )
        for source in ('file', 'string'):
            with self.subTest(source=source):
                if source == 'file':
                    root = oal.parsexml_(io.BytesIO(xml)).getroot()
                else:
                    root = oal.parsexmlstring_(xml)
                self.assertNotIn('EXPANDED_ENTITY_MARKER', ''.join(root.itertext()))

    def test_normal_oal_preserves_unicode_and_standard_xml_escapes(self):
        xml = self._document('Žďár &amp; okolí &#8211; &lt;louka&gt;')
        expected_name = 'Žďár & okolí – <louka>'
        self.assertEqual(oal.parsexmlstring_(xml).findtext('sites/site/name'), expected_name)
        observations = oal.parse(io.BytesIO(xml), silence=True)
        site = observations.get_sites().get_site()[0]
        self.assertEqual(site.get_name(), expected_name)
        self.assertEqual(site.get_longitude().get_valueOf_(), '14.5')
        self.assertEqual(site.get_latitude().get_valueOf_(), '50.0')


if __name__ == '__main__':
    unittest.main()
