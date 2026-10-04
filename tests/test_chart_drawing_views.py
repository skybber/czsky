import io
import json
import unittest

from app import create_app, db
from app.models import ChartDrawing, User
from app.commons.chart_drawings import drawings_to_json, parse_drawings_compact


def _definition(compact='L10_10_11_11*T12_12~A'):
    return json.loads(drawings_to_json(parse_drawings_compact(compact)))


class ChartDrawingViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.owner = self._create_user('drawing-owner')
        self.other_user = self._create_user('other-user')
        self.own_drawing = self._create_drawing(self.owner, 'Mine')
        self.other_private = self._create_drawing(self.other_user, 'Other private')
        self.other_public = self._create_drawing(self.other_user, 'Other public', is_public=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @staticmethod
    def _create_user(name):
        user = User(user_name=name, full_name=name, email=name + '@example.com', password='password', confirmed=True)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def _create_drawing(user, name, is_public=False):
        drawing = ChartDrawing(user_id=user.id, name=name, definition=json.dumps(_definition()),
                               item_count=2, is_public=is_public)
        db.session.add(drawing)
        db.session.commit()
        return drawing

    def _login(self):
        response = self.client.post('/account/login', data={'email': self.owner.email, 'password': 'password'})
        self.assertEqual(302, response.status_code)

    # --- API ---------------------------------------------------------------------------------

    def test_list_returns_only_own_drawings(self):
        self._login()
        response = self.client.get('/chart/drawings')
        self.assertEqual(200, response.status_code)
        self.assertEqual(['Mine'], [d['name'] for d in response.get_json()['items']])

    def test_get_permissions(self):
        self.assertEqual(404, self.client.get('/chart/drawings/{}'.format(self.other_private.id)).status_code)
        anonymous_public = self.client.get('/chart/drawings/{}'.format(self.other_public.id))
        self.assertEqual(200, anonymous_public.status_code)
        self.assertFalse(anonymous_public.get_json()['is_owner'])
        self.assertEqual(2, len(anonymous_public.get_json()['definition']['items']))

        self._login()
        own = self.client.get('/chart/drawings/{}'.format(self.own_drawing.id)).get_json()
        self.assertTrue(own['is_owner'])
        self.assertEqual(404, self.client.get('/chart/drawings/{}'.format(self.other_private.id)).status_code)

    def test_create(self):
        self._login()
        response = self.client.post('/chart/drawings', json={'name': ' Route ', 'definition': _definition('L10_10_20_10')})
        self.assertEqual(201, response.status_code)
        drawing = db.session.get(ChartDrawing, response.get_json()['id'])
        self.assertEqual('Route', drawing.name)
        self.assertEqual(self.owner.id, drawing.user_id)
        self.assertEqual(1, drawing.item_count)
        self.assertAlmostEqual(0.2618, drawing.center_ra, places=3)  # 15 deg
        self.assertGreaterEqual(drawing.fld_size, 12)

    def test_create_validation(self):
        self._login()
        self.assertEqual(400, self.client.post('/chart/drawings', json={'name': '', 'definition': _definition()}).status_code)
        self.assertEqual(400, self.client.post('/chart/drawings', json={'name': 'x', 'definition': {'items': []}}).status_code)
        # Form-encoded body (what a cross-site form could send) is rejected.
        self.assertEqual(400, self.client.post('/chart/drawings', data={'name': 'x'}).status_code)

    def test_create_requires_login(self):
        response = self.client.post('/chart/drawings', json={'name': 'x', 'definition': _definition()})
        self.assertEqual(302, response.status_code)
        self.assertEqual(3, ChartDrawing.query.count())

    def test_update_with_optimistic_locking(self):
        self._login()
        url = '/chart/drawings/{}'.format(self.own_drawing.id)
        base = self.client.get(url).get_json()['update_date']

        ok = self.client.put(url, json={'definition': _definition('T1_1'), 'base_update_date': base})
        self.assertEqual(200, ok.status_code)
        self.assertEqual(1, db.session.get(ChartDrawing, self.own_drawing.id).item_count)

        stale = self.client.put(url, json={'definition': _definition('T2_2'), 'base_update_date': base})
        self.assertEqual(409, stale.status_code)
        self.assertEqual(ok.get_json()['update_date'], stale.get_json()['update_date'])

        forced = self.client.put(url, json={'definition': _definition('T2_2*T3_3'), 'base_update_date': base, 'force': True})
        self.assertEqual(200, forced.status_code)
        self.assertEqual(2, db.session.get(ChartDrawing, self.own_drawing.id).item_count)

    def test_cannot_update_other_users_drawing(self):
        self._login()
        response = self.client.put('/chart/drawings/{}'.format(self.other_public.id),
                                   json={'definition': _definition(), 'force': True})
        self.assertEqual(404, response.status_code)

    # --- management pages --------------------------------------------------------------------

    def test_list_page(self):
        self._login()
        response = self.client.get('/chart-drawings')
        self.assertEqual(200, response.status_code)
        self.assertIn(b'Mine', response.data)
        self.assertNotIn(b'Other public', response.data)
        self.assertIn('dset={}'.format(self.own_drawing.id).encode(), response.data)

    def test_edit_and_publish(self):
        self._login()
        url = '/chart-drawing/{}/edit'.format(self.own_drawing.id)
        self.assertEqual(200, self.client.get(url).status_code)
        response = self.client.post(url, data={'name': 'Renamed', 'description': 'd', 'is_public': 'y'})
        self.assertEqual(302, response.status_code)
        drawing = db.session.get(ChartDrawing, self.own_drawing.id)
        self.assertEqual('Renamed', drawing.name)
        self.assertTrue(drawing.is_public)
        self.assertIn(b'share_url', self.client.get(url).data)

    def test_other_users_drawing_pages_are_404(self):
        self._login()
        for path in ('/chart-drawing/{}/edit', '/chart-drawing/{}/export'):
            self.assertEqual(404, self.client.get(path.format(self.other_public.id)).status_code)
        self.assertEqual(404, self.client.post('/chart-drawing/{}/delete'.format(self.other_public.id)).status_code)
        self.assertIsNotNone(db.session.get(ChartDrawing, self.other_public.id))

    def test_delete_duplicate_export_import(self):
        self._login()
        dup = self.client.post('/chart-drawing/{}/duplicate'.format(self.own_drawing.id))
        self.assertEqual(302, dup.status_code)
        self.assertEqual(2, ChartDrawing.query.filter_by(user_id=self.owner.id).count())

        export = self.client.get('/chart-drawing/{}/export'.format(self.own_drawing.id))
        self.assertEqual('application/json', export.mimetype)
        exported = json.loads(export.data)
        self.assertEqual('Mine', exported['name'])

        imported = self.client.post('/chart-drawings/import', data={
            'file': (io.BytesIO(export.data), 'route.json'),
        }, content_type='multipart/form-data')
        self.assertEqual(302, imported.status_code)
        names = sorted(d.name for d in ChartDrawing.query.filter_by(user_id=self.owner.id))
        self.assertEqual(3, len(names))
        self.assertEqual(2, names.count('Mine'))

        bad = self.client.post('/chart-drawings/import', data={'file': (io.BytesIO(b'[1,2]'), 'x.json')},
                               content_type='multipart/form-data')
        self.assertEqual(302, bad.status_code)
        self.assertEqual(3, ChartDrawing.query.filter_by(user_id=self.owner.id).count())

        delete = self.client.post('/chart-drawing/{}/delete'.format(self.own_drawing.id))
        self.assertEqual(302, delete.status_code)
        self.assertIsNone(db.session.get(ChartDrawing, self.own_drawing.id))


if __name__ == '__main__':
    unittest.main()
