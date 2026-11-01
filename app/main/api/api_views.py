from functools import wraps

from flask import Blueprint, g, jsonify, request

from app.main.usersettings.mcp_token_service import verify_user_mcp_token

from .api_service import dso_detail_payload, dso_status_payload, wishlist_add_payload

main_api = Blueprint('main_api', __name__, url_prefix='/api/v1')


def _bearer_token():
    header = request.headers.get('Authorization', '')
    scheme, _, value = header.partition(' ')
    if scheme.lower() != 'bearer' or not value.strip():
        return None
    return value.strip()


def _error(message, status):
    return jsonify(error=message), status


def token_required(*any_of_scopes):
    """Authenticate request by user API (MCP) token. Token must have at least one of given scopes."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            raw_token = _bearer_token()
            if raw_token is None:
                return _error('missing bearer token', 401)
            token_info = verify_user_mcp_token(raw_token)
            if token_info is None:
                return _error('invalid token', 401)
            scopes = set(token_info['scopes'])
            if any_of_scopes and not scopes.intersection(any_of_scopes):
                return _error('insufficient scope', 403)
            g.api_user_id = token_info['user_id']
            g.api_scopes = scopes
            return func(*args, **kwargs)
        return wrapper
    return decorator


@main_api.after_request
def _no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def _json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


@main_api.route('/dso/status', methods=['POST'])
@token_required('observed:read', 'wishlist:read')
def dso_status():
    body = _json_body()
    if body is None:
        return _error('JSON object body expected', 400)
    try:
        payload = dso_status_payload(
            g.api_user_id,
            body.get('names'),
            include_observed='observed:read' in g.api_scopes,
            include_wishlist='wishlist:read' in g.api_scopes,
        )
    except ValueError as e:
        return _error(str(e), 400)
    return jsonify(payload)


@main_api.route('/dso/detail', methods=['GET'])
@token_required('dso:read', 'observed:read', 'wishlist:read')
def dso_detail():
    try:
        payload = dso_detail_payload(
            g.api_user_id,
            request.args.get('name'),
            include_observed='observed:read' in g.api_scopes,
            include_wishlist='wishlist:read' in g.api_scopes,
        )
    except ValueError as e:
        return _error(str(e), 400)
    if payload is None:
        return _error('object not found', 404)
    return jsonify(payload)


@main_api.route('/wishlist/items', methods=['POST'])
@token_required('wishlist:write')
def wishlist_add():
    body = _json_body()
    if body is None:
        return _error('JSON object body expected', 400)
    try:
        payload = wishlist_add_payload(g.api_user_id, body.get('name'))
    except ValueError as e:
        return _error(str(e), 400)
    if payload is None:
        return _error('object not found', 404)
    return jsonify(payload)
