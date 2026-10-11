import unittest

from app import create_app, db
from app.models import (
    Constellation,
    DeepskyObject,
    Role,
    User,
    UserDsoDescription,
)
from app.main.catalogue import constellation_views, deepskyobject_views


class DsoConstellationViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        for key in ('EDITOR_USER_NAME_CS', 'EDITOR_USER_NAME_EN', 'ALL_EDITORS_USER_NAMES_CS', 'ALL_EDITORS_USER_NAMES_EN'):
            self.app.config[key] = None
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

        self.constellation = Constellation(iau_code='AND', name='Andromeda', season='autumn', label_ra=0.2, label_dec=0.7)
        db.session.add(self.constellation)
        db.session.commit()
        self.dso = DeepskyObject(name='NGC224', type='GX', ra=0.18, dec=0.72, mag=3.4,
                                 constellation_id=self.constellation.id)
        db.session.add(self.dso)
        db.session.commit()

        self.editor = self._create_user('editor', role_name='Editor')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_user(name, role_name=None):
        user = User(user_name=name, full_name=name, email=name + '@example.com', password='password', confirmed=True)
        if role_name:
            user.role = Role.query.filter_by(name=role_name).first()
        db.session.add(user)
        db.session.commit()
        return user

    def _login(self, user):
        response = self.client.post('/account/login', data={'email': user.email, 'password': 'password'})
        self.assertEqual(302, response.status_code)

    # --- deepsky objects ---------------------------------------------------------------------

    def test_switch_wish_list_without_dso_id_returns_404(self):
        self._login(self.editor)
        self.assertEqual(404, self.client.get('/deepskyobject/switch-wish-list').status_code)
        self.assertEqual(404, self.client.get('/deepskyobject/switch-observed-list').status_code)
        self.assertEqual(404, self.client.get('/deepskyobject/switch-session-plan').status_code)

    def test_dso_edit_without_configured_editor_returns_404(self):
        self._login(self.editor)
        self.assertEqual(404, self.client.get('/deepskyobject/{}/edit'.format(self.dso.id)).status_code)

    def test_dso_edit_new_empty_description_is_not_stored(self):
        self.app.config['EDITOR_USER_NAME_CS'] = 'editor'
        self._login(self.editor)
        response = self.client.post('/deepskyobject/{}/edit'.format(self.dso.id),
                                    data={'common_name': '', 'text': '', 'references': '', 'rating': '1', 'goback': 'false'})
        self.assertEqual(302, response.status_code)
        self.assertEqual(0, UserDsoDescription.query.count())

    def test_dso_edit_stores_description(self):
        self.app.config['EDITOR_USER_NAME_CS'] = 'editor'
        self._login(self.editor)
        response = self.client.post('/deepskyobject/{}/edit'.format(self.dso.id),
                                    data={'common_name': 'Andromeda Galaxy', 'text': 'Big spiral', 'references': '',
                                          'rating': '5', 'goback': 'false'})
        self.assertEqual(302, response.status_code)
        descr = UserDsoDescription.query.filter_by(dso_id=self.dso.id, lang_code='cs').first()
        self.assertEqual('Big spiral', descr.text)

    def test_all_deepskyobjects_clears_max_axis_ratio_filter(self):
        self.client.post('/deepskyobjects', data={'max_axis_ratio': '0.5'})
        with self.client.session_transaction() as sess:
            self.assertIn(0.5, sess.values())
        self.client.get('/all-deepskyobjects')
        with self.client.session_transaction() as sess:
            self.assertNotIn(0.5, sess.values())

    def test_create_author_entry_with_deleted_user(self):
        self.assertEqual(('', ''), deepskyobject_views._create_author_entry(9999, None))
        self.assertEqual(('', ''), constellation_views._create_author_entry(9999, None))
        self.assertEqual(('', ''), deepskyobject_views._create_author_entry(None, None))

    # --- constellations ----------------------------------------------------------------------

    def test_constellation_info_without_configured_editor(self):
        response = self.client.get('/constellation/AND/info')
        self.assertEqual(200, response.status_code)

    def test_constellation_info_without_cs_editor(self):
        self.app.config['EDITOR_USER_NAME_EN'] = 'editor'
        response = self.client.get('/constellation/AND/info', headers={'Host': 'www.czsky.eu'})
        self.assertEqual(200, response.status_code)

    def test_constellation_deepskyobjects_without_cs_editor(self):
        response = self.client.get('/constellation/AND/deepskyobjects')
        self.assertEqual(200, response.status_code)

    def test_constellation_edit_without_configured_editor_returns_404(self):
        self._login(self.editor)
        self.assertEqual(404, self.client.get('/constellation/{}/edit'.format(self.constellation.id)).status_code)


if __name__ == '__main__':
    unittest.main()
