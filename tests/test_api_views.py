import io
import json
import threading
import time
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy import event
from werkzeug.test import EnvironBuilder, run_wsgi_app

from app import create_app, db
from app.main.api import api_service
from app.main.usersettings.mcp_token_service import create_user_mcp_token
from app.models import (
    Catalogue,
    DeepskyObject,
    ObservedList,
    User,
    WishList,
    WishListItem,
)


class ApiViewsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # catalogue codes are cached per process, reset the cache to the catalogues of this test database
        db.session.add_all([Catalogue(id=1, code='NGC', name='NGC'), Catalogue(id=2, code='M', name='Messier')])
        db.session.commit()
        Catalogue._catalog_code_map = None
        Catalogue._catalog_id_map = None

        self.user = self._create_user('observer')
        self.other_user = self._create_user('other')

        self.ngc891 = self._add_dso(1, 'NGC891')
        self.m31 = self._add_dso(2, 'M31')
        self.ngc224 = self._add_dso(3, 'NGC224', master=self.m31)
        self.ngc7000 = self._add_dso(4, 'NGC7000')

    def tearDown(self):
        Catalogue._catalog_code_map = None
        Catalogue._catalog_id_map = None
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
    def _add_dso(dso_id, name, master=None):
        dso = DeepskyObject(id=dso_id, name=name, type='GX', ra=0.1, dec=0.1, mag=10.0,
                            master_id=master.id if master else None)
        db.session.add(dso)
        db.session.commit()
        return dso

    def _token(self, scope, user=None):
        _, plain = create_user_mcp_token((user or self.user).id, 'test', scope=scope)
        return {'Authorization': 'Bearer ' + plain}

    def _observe(self, user, dso):
        observed_list = ObservedList.create_get_observed_list_by_user_id(user.id)
        db.session.add(observed_list.create_new_deepsky_object_item(dso.id))
        db.session.commit()

    def _wish(self, user, dso):
        wish_list = WishList.create_get_wishlist_by_user_id(user.id)
        db.session.add(wish_list.create_new_deepsky_object_item(dso.id))
        db.session.commit()

    def _status(self, names, headers):
        return self.client.post('/api/v1/dso/status', json={'names': names}, headers=headers)

    def test_status_requires_token(self):
        self.assertEqual(401, self._status(['NGC891'], {}).status_code)
        self.assertEqual(401, self._status(['NGC891'], {'Authorization': 'Bearer czmcp_bad.token'}).status_code)

    def test_status_requires_read_scope(self):
        response = self._status(['NGC891'], self._token('wishlist:write'))
        self.assertEqual(403, response.status_code)

    def test_status_reports_observed_and_wishlist(self):
        self._observe(self.user, self.ngc891)
        self._wish(self.user, self.ngc7000)
        self._observe(self.other_user, self.ngc7000)

        response = self._status(['NGC891', 'NGC7000', 'NGC9999', ''], self._token('observed:read wishlist:read'))
        self.assertEqual(200, response.status_code)
        objects = response.get_json()['objects']

        self.assertEqual({'found': True, 'dsoId': 1, 'name': 'NGC891', 'observed': True, 'wishlist': False}, objects['NGC891'])
        self.assertEqual({'found': True, 'dsoId': 4, 'name': 'NGC7000', 'observed': False, 'wishlist': True}, objects['NGC7000'])
        self.assertEqual({'found': False}, objects['NGC9999'])
        self.assertNotIn('', objects)

    def test_status_resolves_aliases_to_master(self):
        # observation stored for the child (alias) object counts for the master too
        self._observe(self.user, self.ngc224)
        objects = self._status(['M31', 'NGC224'], self._token('observed:read')).get_json()['objects']
        self.assertEqual(2, objects['M31']['dsoId'])
        self.assertTrue(objects['M31']['observed'])
        self.assertEqual(2, objects['NGC224']['dsoId'])
        self.assertTrue(objects['NGC224']['observed'])
        # wishlist status is not exposed without wishlist:read scope
        self.assertIsNone(objects['M31']['wishlist'])

    @contextmanager
    def _count_selects(self):
        counter = {'selects': 0}

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                counter['selects'] += 1

        event.listen(db.engine, 'before_cursor_execute', before_cursor_execute)
        try:
            yield counter
        finally:
            event.remove(db.engine, 'before_cursor_execute', before_cursor_execute)

    def test_status_uses_constant_number_of_queries(self):
        headers = self._token('observed:read wishlist:read')
        self._status(['NGC891'], headers)   # warm up catalogue cache
        names = ['NGC224', 'M31', 'NGC891', 'Ton 618'] + ['Unknown Object {}'.format(i) for i in range(496)]
        with self._count_selects() as counter:
            response = self._status(names, headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual(500, len(response.get_json()['objects']))
        self.assertLessEqual(counter['selects'], 12)

    def test_status_rejects_invalid_body(self):
        headers = self._token('observed:read')
        self.assertEqual(400, self.client.post('/api/v1/dso/status', data='x', headers=headers).status_code)
        self.assertEqual(400, self._status('NGC891', headers).status_code)
        self.assertEqual(400, self._status(['NGC1'] * 501, headers).status_code)

    def test_wishlist_add_is_idempotent(self):
        headers = self._token('wishlist:write')
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('added', response.get_json()['result'])

        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=headers)
        self.assertEqual('already_present', response.get_json()['result'])
        self.assertEqual(1, WishListItem.query.count())

    def test_wishlist_add_uses_master_and_detects_alias(self):
        headers = self._token('wishlist:write')
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC224'}, headers=headers)
        self.assertEqual({'result': 'added', 'dsoId': 2, 'name': 'M31'}, response.get_json())
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'M31'}, headers=headers)
        self.assertEqual('already_present', response.get_json()['result'])

    def test_wishlist_add_concurrent_requests_create_single_item(self):
        user_id = self.user.id
        headers = self._token('wishlist:write')
        original_check = api_service._wishlist_dso_ids

        def slow_check(*args, **kwargs):
            result = original_check(*args, **kwargs)
            time.sleep(0.3)     # widen the window between existence check and insert
            return result

        results = []
        errors = []

        def add():
            try:
                response = self.app.test_client().post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=headers)
                results.append((response.status_code, response.get_json()))
            except Exception as e:     # pragma: no cover - reported below
                errors.append(e)

        with patch.object(api_service, '_wishlist_dso_ids', side_effect=slow_check):
            threads = [threading.Thread(target=add) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)

        self.assertEqual([], errors)
        self.assertEqual([200, 200], [code for code, _ in results])
        self.assertEqual(['added', 'already_present'], sorted(body['result'] for _, body in results))
        db.session.remove()
        self.assertEqual(1, WishList.query.filter_by(user_id=user_id).count())
        self.assertEqual(1, WishListItem.query.count())

    def test_api_ignores_session_of_unconfirmed_user(self):
        unconfirmed = User(user_name='unconfirmed', full_name='unconfirmed', email='unconfirmed@example.com', password='password',
                           confirmed=False)
        db.session.add(unconfirmed)
        db.session.commit()
        self.app.login_manager.session_protection = None
        try:
            with self.client.session_transaction() as session:
                session['_user_id'] = str(unconfirmed.id)
                session['_fresh'] = True
            # sanity check: session is active and the web part redirects the unconfirmed user
            self.assertIn('/account/unconfirmed', self.client.get('/wish-list').headers.get('Location', ''))

            response = self._status(['NGC891'], self._token('observed:read'))
            self.assertEqual(200, response.status_code)
            self.assertIn('NGC891', response.get_json()['objects'])
            response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=self._token('wishlist:write'))
            self.assertEqual(200, response.status_code)
        finally:
            self.app.login_manager.session_protection = 'strong'

    def _detail(self, name, headers):
        return self.client.get('/api/v1/dso/detail', query_string={'name': name}, headers=headers)

    def test_detail_returns_object_data(self):
        self._observe(self.user, self.ngc224)
        response = self._detail('NGC224', self._token('observed:read'))
        self.assertEqual(200, response.status_code)
        data = response.get_json()
        self.assertEqual(2, data['dsoId'])
        self.assertEqual('M31', data['name'])
        self.assertEqual(['NGC224'], data['otherNames'])
        self.assertEqual('GX', data['type'])
        self.assertEqual(10.0, data['mag'])
        self.assertTrue(data['observed'])
        self.assertIsNone(data['wishlist'])
        self.assertIsNone(data['descriptionHtml'])
        self.assertEqual([], data['apertureDescriptions'])
        self.assertTrue(data['urls']['info'].endswith('/deepskyobject/M31/info'))
        self.assertTrue(data['urls']['chart'].endswith('/deepskyobject/M31/chart'))

    def test_detail_renders_description(self):
        class Descr:
            text = 'Nice **galaxy**, see [link](/x).'
            common_name = 'Edge-on galaxy'
            references = None

        with patch.object(api_service, 'get_dso_descriptions_with_master_fallback', return_value=(Descr(), [('200/250', 'Faint.')], None)):
            data = self._detail('NGC891', self._token('dso:read')).get_json()
        self.assertEqual('Edge-on galaxy', data['commonName'])
        self.assertIn('<strong>galaxy</strong>', data['descriptionHtml'])
        self.assertIn('href="/x"', data['descriptionHtml'])
        self.assertEqual([{'aperture': '200/250mm', 'html': '<p>Faint.</p>\n'}], data['apertureDescriptions'])
        # dso:read alone doesn't expose personal data
        self.assertIsNone(data['observed'])
        self.assertIsNone(data['wishlist'])

    def test_detail_without_token(self):
        self._observe(self.user, self.ngc891)
        response = self._detail('NGC891', {})
        self.assertEqual(200, response.status_code)
        data = response.get_json()
        self.assertEqual('NGC891', data['name'])
        self.assertIsNone(data['observed'])
        self.assertIsNone(data['wishlist'])
        self.assertEqual(404, self._detail('NGC9999', {}).status_code)

    def test_detail_errors(self):
        self.assertEqual(401, self._detail('NGC891', {'Authorization': 'Bearer czmcp_bad.token'}).status_code)
        self.assertEqual(401, self._detail('NGC891', {'Authorization': 'Basic abc'}).status_code)
        self.assertEqual(403, self._detail('NGC891', self._token('wishlist:write')).status_code)
        self.assertEqual(404, self._detail('NGC9999', self._token('dso:read')).status_code)
        self.assertEqual(400, self.client.get('/api/v1/dso/detail', headers=self._token('dso:read')).status_code)

    def test_disabled_or_deleted_user_token_is_rejected(self):
        headers = self._token('observed:read wishlist:write')
        self.assertEqual(200, self._status(['NGC891'], headers).status_code)

        self.user.is_disabled = True
        db.session.commit()
        self.assertEqual(401, self._status(['NGC891'], headers).status_code)
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=headers)
        self.assertEqual(401, response.status_code)
        self.assertEqual(0, WishListItem.query.count())
        # optional authentication: an invalid token is still rejected, not served anonymously
        self.assertEqual(401, self._detail('NGC891', headers).status_code)

        self.user.is_disabled = False
        self.user.is_deleted = True
        db.session.commit()
        self.assertEqual(401, self._status(['NGC891'], headers).status_code)

    def test_too_large_body_is_rejected(self):
        headers = self._token('observed:read')
        big = {'names': ['NGC891'], 'padding': 'x' * (300 * 1024)}
        response = self._status(big['names'], headers)
        self.assertEqual(200, response.status_code)
        response = self.client.post('/api/v1/dso/status', json=big, headers=headers)
        self.assertEqual(413, response.status_code)
        # rejected before authentication, so even without a token
        self.assertEqual(413, self.client.post('/api/v1/dso/status', json=big).status_code)

    def test_too_large_chunked_body_is_rejected(self):
        headers = dict(self._token('observed:read'))
        headers['Content-Type'] = 'application/json'
        payload = ('{"names": ["NGC891"], "padding": "' + 'x' * (300 * 1024) + '"}').encode()

        def post_chunked(body):
            # chunked transfer: no Content-Length, the server (e.g. gunicorn) marks the input as terminated.
            # The WSGI app is called directly, because the test client would add Content-Length again.
            builder = EnvironBuilder(path='/api/v1/dso/status', method='POST', input_stream=io.BytesIO(body), headers=headers)
            environ = builder.get_environ()
            environ.pop('CONTENT_LENGTH', None)
            environ['wsgi.input_terminated'] = True
            app_iter, status, _ = run_wsgi_app(self.app.wsgi_app, environ)
            return int(status.split()[0]), json.loads(b''.join(app_iter))

        status, body = post_chunked(payload)
        self.assertEqual(413, status)
        self.assertEqual('request body too large', body['error'])
        status, body = post_chunked(b'{"names": ["NGC891"]}')
        self.assertEqual(200, status)
        self.assertIn('NGC891', body['objects'])

    def test_api_is_csrf_exempt(self):
        self.app.config['WTF_CSRF_ENABLED'] = True
        try:
            response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=self._token('wishlist:write'))
        finally:
            self.app.config['WTF_CSRF_ENABLED'] = False
        self.assertEqual(200, response.status_code)

    def test_wishlist_add_requires_write_scope(self):
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC891'}, headers=self._token('wishlist:read'))
        self.assertEqual(403, response.status_code)

    def test_wishlist_add_unknown_object(self):
        response = self.client.post('/api/v1/wishlist/items', json={'name': 'NGC9999'}, headers=self._token('wishlist:write'))
        self.assertEqual(404, response.status_code)
        response = self.client.post('/api/v1/wishlist/items', json={}, headers=self._token('wishlist:write'))
        self.assertEqual(400, response.status_code)


if __name__ == '__main__':
    unittest.main()
