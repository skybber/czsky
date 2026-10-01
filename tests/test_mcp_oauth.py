import base64
import hashlib
import os
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text

from app import create_app, db
from app.main.usersettings.mcp_token_service import create_user_mcp_token, verify_user_mcp_token
from app.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthRefreshTokenHistory,
    McpUserToken,
    User,
)

REDIRECT_URI = 'http://127.0.0.1:33418/callback'
CODE_VERIFIER = 'v' * 64
CODE_CHALLENGE = base64.urlsafe_b64encode(
    hashlib.sha256(CODE_VERIFIER.encode('ascii')).digest()
).rstrip(b'=').decode('ascii')

ENV = {
    'MCP_AUTH_ISSUER_URL': 'https://www.czsky.cz',
    'MCP_AUTH_RESOURCE_SERVER_URL': 'https://www.czsky.cz/mcp',
}


class McpOAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.env_patch = mock.patch.dict(os.environ, ENV)
        self.env_patch.start()
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(
            user_name='oauth-user',
            full_name='OAuth User',
            email='oauth-user@example.com',
            password='password',
            confirmed=True,
        )
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        self.env_patch.stop()

    def _login(self):
        response = self.client.post('/account/login', data={
            'email': self.user.email,
            'password': 'password',
        })
        self.assertEqual(302, response.status_code)

    def _register(self, **metadata):
        payload = {'redirect_uris': [REDIRECT_URI], 'client_name': 'Test client'}
        payload.update(metadata)
        response = self.client.post('/oauth/register', json=payload)
        self.assertEqual(201, response.status_code, response.data)
        return response.get_json()

    def _authorize_params(self, client_id, **overrides):
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': REDIRECT_URI,
            'code_challenge': CODE_CHALLENGE,
            'code_challenge_method': 'S256',
            'scope': 'wishlist:read dso:read',
            'state': 'xyz',
            'resource': 'https://www.czsky.cz/mcp',
        }
        params.update(overrides)
        return params

    def _get_code(self, client_id):
        self._login()
        response = self.client.post(
            '/oauth/authorize',
            query_string=self._authorize_params(client_id),
            data={'allow': 'Allow'},
        )
        self.assertEqual(302, response.status_code)
        query = parse_qs(urlparse(response.headers['Location']).query)
        self.assertEqual(['xyz'], query['state'])
        return query['code'][0]

    def _exchange(self, client_id, code, verifier=CODE_VERIFIER):
        return self.client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'code_verifier': verifier,
        })

    def test_metadata_uses_configured_issuer(self):
        response = self.client.get('/.well-known/oauth-authorization-server')
        self.assertEqual(200, response.status_code)
        metadata = response.get_json()
        self.assertEqual('https://www.czsky.cz', metadata['issuer'])
        self.assertEqual('https://www.czsky.cz/oauth/token', metadata['token_endpoint'])
        self.assertEqual(['S256'], metadata['code_challenge_methods_supported'])
        self.assertIn('wishlist:read', metadata['scopes_supported'])

    def test_register_rejects_non_loopback_http_redirect(self):
        response = self.client.post('/oauth/register', json={'redirect_uris': ['http://evil.example.com/cb']})
        self.assertEqual(400, response.status_code)
        self.assertEqual('invalid_redirect_uri', response.get_json()['error'])

    def test_authorize_requires_login(self):
        client_id = self._register()['client_id']
        response = self.client.get('/oauth/authorize', query_string=self._authorize_params(client_id))
        self.assertEqual(302, response.status_code)
        self.assertIn('/account/login', response.headers['Location'])

    def test_authorize_unknown_redirect_uri_is_not_redirected(self):
        client_id = self._register()['client_id']
        self._login()
        response = self.client.get(
            '/oauth/authorize',
            query_string=self._authorize_params(client_id, redirect_uri='https://evil.example.com/cb'),
        )
        self.assertEqual(400, response.status_code)

    def test_authorize_without_pkce_redirects_with_error(self):
        client_id = self._register()['client_id']
        self._login()
        response = self.client.get(
            '/oauth/authorize',
            query_string=self._authorize_params(client_id, code_challenge=''),
        )
        self.assertEqual(302, response.status_code)
        self.assertIn('error=invalid_request', response.headers['Location'])

    def test_authorize_shows_consent_page(self):
        client_id = self._register()['client_id']
        self._login()
        response = self.client.get('/oauth/authorize', query_string=self._authorize_params(client_id))
        self.assertEqual(200, response.status_code)
        self.assertIn(b'Test client', response.data)
        self.assertEqual('DENY', response.headers['X-Frame-Options'])

    def test_deny_redirects_with_access_denied(self):
        client_id = self._register()['client_id']
        self._login()
        response = self.client.post(
            '/oauth/authorize',
            query_string=self._authorize_params(client_id),
            data={'deny': 'Deny'},
        )
        self.assertEqual(302, response.status_code)
        self.assertIn('error=access_denied', response.headers['Location'])

    def test_full_flow_issues_verifiable_token_and_refreshes(self):
        client_id = self._register()['client_id']
        code = self._get_code(client_id)

        response = self._exchange(client_id, code)
        self.assertEqual(200, response.status_code, response.data)
        tokens = response.get_json()
        self.assertEqual('Bearer', tokens['token_type'])
        self.assertEqual('wishlist:read dso:read', tokens['scope'])

        verified = verify_user_mcp_token(tokens['access_token'])
        self.assertEqual(self.user.id, verified['user_id'])
        self.assertEqual(['dso:read', 'wishlist:read'], verified['scopes'])

        response = self.client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'refresh_token': tokens['refresh_token'],
        })
        self.assertEqual(200, response.status_code, response.data)
        refreshed = response.get_json()
        self.assertIsNotNone(verify_user_mcp_token(refreshed['access_token']))
        self.assertIsNone(verify_user_mcp_token(tokens['access_token']))

        # Rotated refresh token cannot be reused.
        response = self.client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'refresh_token': tokens['refresh_token'],
        })
        self.assertEqual(400, response.status_code)

    def test_wrong_code_verifier_is_rejected(self):
        client_id = self._register()['client_id']
        code = self._get_code(client_id)
        response = self._exchange(client_id, code, verifier='w' * 64)
        self.assertEqual(400, response.status_code)
        self.assertEqual('invalid_grant', response.get_json()['error'])

    def test_code_replay_revokes_issued_token(self):
        client_id = self._register()['client_id']
        code = self._get_code(client_id)
        tokens = self._exchange(client_id, code).get_json()

        response = self._exchange(client_id, code)
        self.assertEqual(400, response.status_code)
        self.assertIsNone(verify_user_mcp_token(tokens['access_token']))

    def test_confidential_client_requires_secret(self):
        registered = self._register(token_endpoint_auth_method='client_secret_post')
        code = self._get_code(registered['client_id'])

        response = self._exchange(registered['client_id'], code)
        self.assertEqual(401, response.status_code)

        code = self._get_code(registered['client_id'])
        response = self.client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'client_id': registered['client_id'],
            'client_secret': registered['client_secret'],
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'code_verifier': CODE_VERIFIER,
        })
        self.assertEqual(200, response.status_code, response.data)

    def test_revoke_invalidates_access_token(self):
        client_id = self._register()['client_id']
        tokens = self._exchange(client_id, self._get_code(client_id)).get_json()

        response = self.client.post('/oauth/revoke', data={
            'client_id': client_id,
            'token': tokens['refresh_token'],
        })
        self.assertEqual(200, response.status_code)
        self.assertIsNone(verify_user_mcp_token(tokens['access_token']))


    def _refresh(self, client_id, refresh_token):
        return self.client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'refresh_token': refresh_token,
        })

    def test_concurrently_consumed_code_is_rejected(self):
        client_id = self._register()['client_id']
        code = self._get_code(client_id)
        # Load the row into the session, then let a "concurrent request" consume it
        # behind the session's back, so the loaded object still says is_used=False.
        code_row = McpOAuthAuthorizationCode.query.one()
        self.assertFalse(code_row.is_used)
        db.session.execute(text('UPDATE mcp_oauth_authorization_codes SET is_used = 1'))

        response = self._exchange(client_id, code)
        self.assertEqual(400, response.status_code)
        self.assertEqual('invalid_grant', response.get_json()['error'])
        self.assertEqual(0, McpUserToken.query.count())

    def test_refresh_token_replay_revokes_whole_grant(self):
        client_id = self._register()['client_id']
        tokens = self._exchange(client_id, self._get_code(client_id)).get_json()

        # Attacker uses the stolen refresh token first.
        attacker = self._refresh(client_id, tokens['refresh_token']).get_json()
        self.assertIsNotNone(verify_user_mcp_token(attacker['access_token']))

        # Legitimate client replays the now rotated token -> whole grant is revoked.
        response = self._refresh(client_id, tokens['refresh_token'])
        self.assertEqual(400, response.status_code)
        self.assertIsNone(verify_user_mcp_token(attacker['access_token']))
        self.assertEqual(400, self._refresh(client_id, attacker['refresh_token']).status_code)

    def test_code_consumption_is_committed_together_with_token(self):
        from app.main.oauth import oauth_service

        client_id = self._register()['client_id']
        code = self._get_code(client_id)
        client = oauth_service.get_client(client_id)

        with mock.patch.object(oauth_service, 'generate_unique_token_id', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                oauth_service.exchange_authorization_code(client, code, REDIRECT_URI, CODE_VERIFIER)
        db.session.rollback()

        # No intermediate commit: the failed issue left the code unconsumed.
        self.assertFalse(McpOAuthAuthorizationCode.query.one().is_used)

    def test_forged_refresh_secret_does_not_revoke_grant(self):
        client_id = self._register()['client_id']
        tokens = self._exchange(client_id, self._get_code(client_id)).get_json()

        # token_id is visible in the access token; a forged secret must not revoke the grant.
        token_id = tokens['access_token'][len('czmcp_'):].split('.', 1)[0]
        response = self._refresh(client_id, f'czmcpr_{token_id}.' + 'x' * 43)
        self.assertEqual(400, response.status_code)
        self.assertIsNotNone(verify_user_mcp_token(tokens['access_token']))
        self.assertEqual(200, self._refresh(client_id, tokens['refresh_token']).status_code)

    def test_replay_after_multiple_rotations_revokes_grant(self):
        client_id = self._register()['client_id']
        tokens = self._exchange(client_id, self._get_code(client_id)).get_json()

        latest = tokens
        for _ in range(3):
            latest = self._refresh(client_id, latest['refresh_token']).get_json()

        self.assertEqual(400, self._refresh(client_id, tokens['refresh_token']).status_code)
        self.assertIsNone(verify_user_mcp_token(latest['access_token']))

    def test_token_endpoint_rejects_foreign_resource(self):
        client_id = self._register()['client_id']
        self._login()
        response = self.client.post(
            '/oauth/authorize',
            query_string=self._authorize_params(client_id, resource=''),
            data={'allow': 'Allow'},
        )
        code = parse_qs(urlparse(response.headers['Location']).query)['code'][0]

        response = self.client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'code_verifier': CODE_VERIFIER,
            'resource': 'https://attacker.example/mcp',
        })
        self.assertEqual(400, response.status_code)
        self.assertEqual('invalid_target', response.get_json()['error'])

    def test_resource_rejected_when_not_configured(self):
        client_id = self._register()['client_id']
        self._login()
        with mock.patch.dict(os.environ, {'MCP_AUTH_RESOURCE_SERVER_URL': ''}):
            response = self.client.get('/oauth/authorize', query_string=self._authorize_params(client_id))
        self.assertEqual(302, response.status_code)
        self.assertIn('error=invalid_target', response.headers['Location'])

    def test_cleanup_removes_only_dead_data(self):
        from datetime import datetime, timedelta
        from app.main.oauth.oauth_service import cleanup_oauth_data

        client_id = self._register()['client_id']
        tokens = self._exchange(client_id, self._get_code(client_id)).get_json()
        self._refresh(client_id, tokens['refresh_token'])
        dead_client_id = self._register(client_name='Never used')['client_id']
        own_pat, _ = create_user_mcp_token(self.user.id, 'personal')
        own_pat.is_revoked = True
        own_pat.update_date = datetime.now() - timedelta(days=365)
        db.session.commit()

        # Fresh data survives.
        self.assertEqual(
            {'authorization_codes': 0, 'refresh_token_history': 0, 'tokens': 0, 'clients': 0},
            cleanup_oauth_data(),
        )

        # Two days later: used code and never used client are gone, grant stays.
        result = cleanup_oauth_data(now=datetime.now() + timedelta(days=2))
        self.assertEqual(1, result['authorization_codes'])
        self.assertEqual(1, result['clients'])
        self.assertIsNone(McpOAuthClient.query.filter_by(client_id=dead_client_id).first())
        self.assertIsNotNone(McpOAuthClient.query.filter_by(client_id=client_id).first())
        self.assertEqual(1, McpOAuthRefreshTokenHistory.query.count())

        # Revoked grant is deleted after 30 days with its history; personal token is kept.
        oauth_row = McpUserToken.query.filter(McpUserToken.oauth_client_id.isnot(None)).one()
        oauth_row.is_revoked = True
        db.session.commit()
        result = cleanup_oauth_data(now=datetime.now() + timedelta(days=31))
        self.assertEqual(1, result['tokens'])
        self.assertEqual(0, McpOAuthRefreshTokenHistory.query.count())
        self.assertIsNotNone(db.session.get(McpUserToken, own_pat.id))

    def test_delete_token_from_settings(self):
        other = User(user_name='other', full_name='Other', email='other@example.com',
                     password='password', confirmed=True)
        db.session.add(other)
        db.session.commit()
        own_row, own_token = create_user_mcp_token(self.user.id, 'own')
        other_row, _ = create_user_mcp_token(other.id, 'other')
        own_id, other_id = own_row.id, other_row.id
        self._login()

        response = self.client.post(f'/user-settings/mcp-token/{other_id}/delete')
        self.assertEqual(302, response.status_code)
        self.assertIsNotNone(db.session.get(McpUserToken, other_id))

        response = self.client.post(f'/user-settings/mcp-token/{own_id}/delete')
        self.assertEqual(302, response.status_code)
        self.assertIsNone(db.session.get(McpUserToken, own_id))
        self.assertIsNone(verify_user_mcp_token(own_token))

        response = self.client.get('/user-settings/mcp-token')
        self.assertEqual(200, response.status_code)


if __name__ == '__main__':
    unittest.main()
