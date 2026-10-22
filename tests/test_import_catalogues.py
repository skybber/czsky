import os
import tempfile
import unittest

from app import create_app, db
from app.models.catalogue import Catalogue
from imports.import_catalogues import import_catalogues


class ImportCataloguesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        self.tmp_dir.cleanup()

    def _write_csv(self, content):
        path = os.path.join(self.tmp_dir.name, 'catalogues.csv')
        with open(path, 'w') as f:
            f.write(content)
        return path

    def test_renamed_catalogue_is_updated_by_id(self):
        db.session.add(Catalogue(id=1, code='M', name='Messier catalogue', descr='old'))
        db.session.add(Catalogue(id=61, code='QSO', name='Bright quasars', descr='old'))
        db.session.commit()

        import_catalogues(self._write_csv(
            'id;code;name;description\n'
            '1;M;Messier catalogue;Messier objects\n'
            '\n'
            '61;QSO;Quasars;Quasars from Milliquas\n'
            '62;NEW;New catalogue\n'
        ))

        catalogues = {c.id: c for c in Catalogue.query.all()}
        self.assertEqual(sorted(catalogues), [1, 61, 62])
        self.assertEqual((catalogues[61].code, catalogues[61].name, catalogues[61].descr),
                         ('QSO', 'Quasars', 'Quasars from Milliquas'))
        self.assertEqual(catalogues[1].descr, 'Messier objects')
        self.assertEqual((catalogues[62].code, catalogues[62].name), ('NEW', 'New catalogue'))

    def test_project_catalogues_import_is_repeatable(self):
        import_catalogues('data/astro_catalogues.csv')
        count = Catalogue.query.count()
        import_catalogues('data/astro_catalogues.csv')
        self.assertEqual(Catalogue.query.count(), count)
        self.assertEqual(Catalogue.query.filter_by(id=61).first().code, 'QSO')


if __name__ == '__main__':
    unittest.main()
