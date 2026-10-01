from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import csrf
from .oauth_forms import OAuthConsentForm
from .oauth_service import (
    OAuthError,
    authenticate_client,
    build_authorization_server_metadata,
    create_authorization_code,
    exchange_authorization_code,
    get_issuer_url,
    refresh_access_token,
    register_client,
    revoke_token,
    validate_authorization_params,
    validate_authorization_request,
)

main_oauth = Blueprint('main_oauth', __name__)


def _json_response(payload, status_code=200):
    response = make_response(jsonify(payload), status_code)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


def _error_response(error: OAuthError):
    response = _json_response(error.to_dict(), error.status_code)
    if error.status_code == 401:
        response.headers['WWW-Authenticate'] = 'Basic realm="oauth"'
    return response


def _cors_preflight():
    response = make_response('', 204)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, mcp-protocol-version'
    return response


def _redirect_with(redirect_uri, params):
    separator = '&' if urlparse(redirect_uri).query else '?'
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return redirect(f'{redirect_uri}{separator}{query}')


def _client_credentials():
    if request.authorization and request.authorization.type == 'basic':
        return request.authorization.username, request.authorization.password
    return request.form.get('client_id'), request.form.get('client_secret')


@main_oauth.route('/.well-known/oauth-authorization-server', methods=['GET', 'OPTIONS'])
@main_oauth.route('/.well-known/oauth-authorization-server/<path:_suffix>', methods=['GET', 'OPTIONS'])
def authorization_server_metadata(_suffix=None):
    if request.method == 'OPTIONS':
        return _cors_preflight()
    issuer = get_issuer_url(request.url_root)
    response = _json_response(build_authorization_server_metadata(issuer))
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


@main_oauth.route('/oauth/register', methods=['POST', 'OPTIONS'])
@csrf.exempt
def oauth_register():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        _, payload = register_client(request.get_json(silent=True))
    except OAuthError as e:
        return _error_response(e)
    return _json_response(payload, 201)


@main_oauth.route('/oauth/authorize', methods=['GET', 'POST'])
@login_required
def oauth_authorize():
    try:
        validated = validate_authorization_request(request.args)
    except OAuthError as e:
        # Unknown client or redirect_uri: never redirect, show the error to the user.
        return render_template('main/oauth/oauth_error.html', error=e), 400

    client = validated['client']
    redirect_uri = validated['redirect_uri']
    state = request.args.get('state')

    try:
        params = validate_authorization_params(client, request.args)
    except OAuthError as e:
        return _redirect_with(redirect_uri, {'error': e.error, 'error_description': e.description, 'state': state})

    form = OAuthConsentForm()
    if form.validate_on_submit():
        if not form.allow.data:
            return _redirect_with(redirect_uri, {'error': 'access_denied', 'state': state})
        code = create_authorization_code(
            client=client,
            user_id=current_user.id,
            redirect_uri=redirect_uri,
            scope=params['scope'],
            code_challenge=params['code_challenge'],
            resource=params['resource'],
        )
        return _redirect_with(redirect_uri, {
            'code': code,
            'state': state,
            'iss': get_issuer_url(request.url_root),
        })

    response = make_response(render_template(
        'main/oauth/oauth_authorize.html',
        form=form,
        client=client,
        redirect_host=urlparse(redirect_uri).netloc or redirect_uri,
        scopes=params['scope'].split(),
    ))
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'none'"
    return response


@main_oauth.route('/oauth/token', methods=['POST', 'OPTIONS'])
@csrf.exempt
def oauth_token():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        client = authenticate_client(*_client_credentials())
        grant_type = request.form.get('grant_type')
        if grant_type == 'authorization_code':
            payload = exchange_authorization_code(
                client,
                code=request.form.get('code'),
                redirect_uri=request.form.get('redirect_uri'),
                code_verifier=request.form.get('code_verifier'),
                resource=request.form.get('resource'),
            )
        elif grant_type == 'refresh_token':
            payload = refresh_access_token(
                client,
                refresh_token=request.form.get('refresh_token'),
                scope=request.form.get('scope'),
                resource=request.form.get('resource'),
            )
        else:
            raise OAuthError('unsupported_grant_type', f'Unsupported grant_type: {grant_type}')
    except OAuthError as e:
        return _error_response(e)
    return _json_response(payload)


@main_oauth.route('/oauth/revoke', methods=['POST', 'OPTIONS'])
@csrf.exempt
def oauth_revoke():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        client = authenticate_client(*_client_credentials())
    except OAuthError as e:
        return _error_response(e)
    revoke_token(client, request.form.get('token'))
    return _json_response({})
