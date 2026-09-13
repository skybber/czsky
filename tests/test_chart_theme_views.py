import unittest

from app import create_app, db
from app.models import ChartTheme, DefaultThemeType, User


class ChartThemeViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.owner = User(
            user_name='theme-owner',
            full_name='Theme Owner',
            email='theme-owner@example.com',
            password='password',
            confirmed=True,
        )
        self.other_user = User(
            user_name='other-user',
            full_name='Other User',
            email='other-user@example.com',
            password='password',
            confirmed=True,
        )
        db.session.add_all([self.owner, self.other_user])
        db.session.commit()

        self.first_theme = self._create_theme(self.owner, 'First theme', 1)
        self.second_theme = self._create_theme(self.owner, 'Second theme', 2)
        self.other_theme = self._create_theme(self.other_user, 'Other theme', 1)

        response = self.client.post('/account/login', data={
            'email': self.owner.email,
            'password': 'password',
        })
        self.assertEqual(302, response.status_code)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_theme(user, name, order):
        theme = ChartTheme(
            name=name,
            default_type=DefaultThemeType.DARK,
            definition='{}',
            order=order,
            user_id=user.id,
            is_active=True,
            is_public=False,
        )
        db.session.add(theme)
        db.session.commit()
        return theme

    def test_edit_page_contains_delete_form(self):
        response = self.client.get(
            '/chart-theme/{}/edit'.format(self.first_theme.id)
        )

        self.assertEqual(200, response.status_code)
        self.assertIn(b'id="bdelete"', response.data)
        self.assertIn(
            '/chart-theme/{}/delete'.format(self.first_theme.id).encode(),
            response.data,
        )
        self.assertIn(b'method="POST"', response.data)

    def test_user_cannot_edit_or_delete_another_users_theme(self):
        edit_response = self.client.get(
            '/chart-theme/{}/edit'.format(self.other_theme.id)
        )
        delete_response = self.client.post(
            '/chart-theme/{}/delete'.format(self.other_theme.id)
        )

        self.assertEqual(404, edit_response.status_code)
        self.assertEqual(404, delete_response.status_code)
        self.assertIsNotNone(db.session.get(ChartTheme, self.other_theme.id))

    def test_delete_owned_theme_resets_session_and_theme_order(self):
        deleted_theme_id = self.first_theme.id
        with self.client.session_transaction() as client_session:
            client_session['cur_custom_theme_id'] = deleted_theme_id
            client_session['cur_custom_theme_name'] = self.first_theme.name
            client_session['theme'] = 'night'

        response = self.client.post(
            '/chart-theme/{}/delete'.format(deleted_theme_id)
        )

        self.assertEqual(302, response.status_code)
        self.assertTrue(response.location.endswith('/chart-themes'))
        self.assertIsNone(db.session.get(ChartTheme, deleted_theme_id))
        self.assertEqual(1, self.second_theme.order)
        with self.client.session_transaction() as client_session:
            self.assertNotIn('cur_custom_theme_id', client_session)
            self.assertNotIn('cur_custom_theme_name', client_session)
            self.assertEqual('dark', client_session['theme'])

    def test_delete_endpoint_rejects_get(self):
        response = self.client.get(
            '/chart-theme/{}/delete'.format(self.first_theme.id)
        )

        self.assertEqual(405, response.status_code)


if __name__ == '__main__':
    unittest.main()
