"""OAuth 2.1 authorization server for MCP clients.

Issues the same ``czmcp_`` bearer tokens as personal MCP tokens, so the MCP
server verifies both through ``verify_user_mcp_token``. Supports dynamic client
registration (RFC 7591), authorization code + PKCE S256 and rotating refresh
tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.main.usersettings.mcp_token_service import (
    SUPPORTED_SCOPES,
    build_plain_mcp_token,
    generate_secret,
    generate_unique_token_id,
    parse_plain_mcp_token,
)
from app.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthRefreshTokenHistory,
    McpUserToken,
)

REFRESH_TOKEN_PREFIX = "czmcpr_"
ACCESS_TOKEN_TTL_SECONDS = 3600
REFRESH_TOKEN_TTL_DAYS = 90
AUTHORIZATION_CODE_TTL_SECONDS = 300

AUTH_METHOD_NONE = "none"
SECRET_AUTH_METHODS = ("client_secret_post", "client_secret_basic")
SUPPORTED_AUTH_METHODS = (AUTH_METHOD_NONE,) + SECRET_AUTH_METHODS

MAX_REDIRECT_URIS = 10
MAX_REDIRECT_URI_LENGTH = 512
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
FORBIDDEN_REDIRECT_SCHEMES = {"javascript", "data", "file", "vbscript"}
CODE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status_code: int = 400):
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code

    def to_dict(self) -> dict[str, str]:
        return {"error": self.error, "error_description": self.description}


def get_issuer_url(default: str) -> str:
    return (os.getenv("MCP_AUTH_ISSUER_URL") or default).rstrip("/")


def get_resource_url() -> str | None:
    resource_url = os.getenv("MCP_AUTH_RESOURCE_SERVER_URL")
    return resource_url.rstrip("/") if resource_url else None


def build_authorization_server_metadata(issuer: str) -> dict[str, Any]:
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "revocation_endpoint": f"{issuer}/oauth/revoke",
        "scopes_supported": list(SUPPORTED_SCOPES),
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": list(SUPPORTED_AUTH_METHODS),
        "revocation_endpoint_auth_methods_supported": list(SUPPORTED_AUTH_METHODS),
    }


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_loopback_http(parsed) -> bool:
    return parsed.scheme == "http" and (parsed.hostname or "") in LOOPBACK_HOSTS


def validate_redirect_uri(uri: Any) -> str:
    if not isinstance(uri, str) or not uri or len(uri) > MAX_REDIRECT_URI_LENGTH:
        raise OAuthError("invalid_redirect_uri", "redirect_uri must be a non-empty string")
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if not scheme or scheme in FORBIDDEN_REDIRECT_SCHEMES:
        raise OAuthError("invalid_redirect_uri", f"Unsupported redirect_uri: {uri}")
    if parsed.fragment:
        raise OAuthError("invalid_redirect_uri", "redirect_uri must not contain a fragment")
    if scheme == "http" and not _is_loopback_http(parsed):
        raise OAuthError("invalid_redirect_uri", "http redirect_uri is allowed only for loopback hosts")
    if scheme in ("http", "https") and not parsed.netloc:
        raise OAuthError("invalid_redirect_uri", f"Invalid redirect_uri: {uri}")
    return uri


def normalize_requested_scope(scope: str | None, fallback: str | None = None) -> str:
    """Keep supported scopes only. Empty request falls back to client/all scopes."""
    requested = (scope or "").split()
    if not requested:
        requested = (fallback or "").split() or list(SUPPORTED_SCOPES)
    granted = [s for s in dict.fromkeys(requested) if s in SUPPORTED_SCOPES]
    if not granted:
        raise OAuthError("invalid_scope", "No supported scope requested")
    return " ".join(granted)


def register_client(metadata: Any) -> tuple[McpOAuthClient, dict[str, Any]]:
    if not isinstance(metadata, dict):
        raise OAuthError("invalid_client_metadata", "Request body must be a JSON object")

    redirect_uris = metadata.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise OAuthError("invalid_redirect_uri", "redirect_uris must be a non-empty list")
    if len(redirect_uris) > MAX_REDIRECT_URIS:
        raise OAuthError("invalid_redirect_uri", "Too many redirect_uris")
    redirect_uris = list(dict.fromkeys(validate_redirect_uri(uri) for uri in redirect_uris))

    auth_method = metadata.get("token_endpoint_auth_method") or AUTH_METHOD_NONE
    if auth_method not in SUPPORTED_AUTH_METHODS:
        raise OAuthError("invalid_client_metadata", f"Unsupported token_endpoint_auth_method: {auth_method}")

    grant_types = metadata.get("grant_types") or ["authorization_code", "refresh_token"]
    if not isinstance(grant_types, list) or "authorization_code" not in grant_types:
        raise OAuthError("invalid_client_metadata", "grant_types must include authorization_code")
    response_types = metadata.get("response_types") or ["code"]
    if not isinstance(response_types, list) or "code" not in response_types:
        raise OAuthError("invalid_client_metadata", "response_types must include code")

    client_name = metadata.get("client_name")
    client_name = client_name.strip()[:128] if isinstance(client_name, str) and client_name.strip() else None
    scope = metadata.get("scope")
    scope = normalize_requested_scope(scope) if isinstance(scope, str) and scope.strip() else None

    client_id = secrets.token_urlsafe(24)
    client_secret = generate_secret() if auth_method in SECRET_AUTH_METHODS else None

    client = McpOAuthClient(
        client_id=client_id,
        client_name=client_name,
        client_secret_hash=generate_password_hash(client_secret) if client_secret else None,
        token_endpoint_auth_method=auth_method,
        redirect_uris="\n".join(redirect_uris),
        scope=scope,
        create_date=datetime.now(),
    )
    db.session.add(client)
    db.session.commit()

    response = {
        "client_id": client_id,
        "client_id_issued_at": int(client.create_date.timestamp()),
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": auth_method,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    if client_name:
        response["client_name"] = client_name
    if scope:
        response["scope"] = scope
    if client_secret:
        response["client_secret"] = client_secret
        response["client_secret_expires_at"] = 0
    return client, response


def get_client(client_id: str | None) -> McpOAuthClient | None:
    if not client_id:
        return None
    return McpOAuthClient.query.filter_by(client_id=client_id).first()


def authenticate_client(client_id: str | None, client_secret: str | None) -> McpOAuthClient:
    client = get_client(client_id)
    if client is None:
        raise OAuthError("invalid_client", "Unknown client", status_code=401)
    if client.client_secret_hash:
        if not client_secret or not check_password_hash(client.client_secret_hash, client_secret):
            raise OAuthError("invalid_client", "Client authentication failed", status_code=401)
    return client


def _redirect_uri_matches(registered: str, requested: str) -> bool:
    if registered == requested:
        return True
    # RFC 8252 7.3: native apps on loopback may use any port.
    reg, req = urlparse(registered), urlparse(requested)
    return (
        _is_loopback_http(reg) and _is_loopback_http(req)
        and reg.hostname == req.hostname
        and reg.path == req.path
        and reg.query == req.query
    )


def resolve_redirect_uri(client: McpOAuthClient, redirect_uri: str | None) -> str:
    registered = client.redirect_uri_list()
    if not redirect_uri:
        if len(registered) == 1:
            return registered[0]
        raise OAuthError("invalid_request", "redirect_uri is required")
    if not any(_redirect_uri_matches(uri, redirect_uri) for uri in registered):
        raise OAuthError("invalid_request", "redirect_uri is not registered for this client")
    return redirect_uri


def validate_resource(resource: str | None) -> str | None:
    if not resource:
        return None
    expected = get_resource_url()
    if not expected or resource.rstrip("/") != expected:
        raise OAuthError("invalid_target", "Unknown resource")
    return expected


def validate_authorization_request(params) -> dict[str, Any]:
    """Validate client and redirect_uri first; errors there must not redirect."""
    client = get_client(params.get("client_id"))
    if client is None:
        raise OAuthError("invalid_client", "Unknown client")
    redirect_uri = resolve_redirect_uri(client, params.get("redirect_uri"))
    return {"client": client, "redirect_uri": redirect_uri}


def validate_authorization_params(client: McpOAuthClient, params) -> dict[str, Any]:
    """Validate the rest; errors here are reported to the redirect_uri."""
    if params.get("response_type") != "code":
        raise OAuthError("unsupported_response_type", "Only response_type=code is supported")
    code_challenge = params.get("code_challenge")
    if not code_challenge or not CODE_VERIFIER_PATTERN.match(code_challenge):
        raise OAuthError("invalid_request", "code_challenge is required (PKCE)")
    if params.get("code_challenge_method") != "S256":
        raise OAuthError("invalid_request", "code_challenge_method must be S256")
    return {
        "scope": normalize_requested_scope(params.get("scope"), client.scope),
        "code_challenge": code_challenge,
        "resource": validate_resource(params.get("resource")),
        "state": params.get("state"),
    }


def create_authorization_code(
    client: McpOAuthClient,
    user_id: int,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    resource: str | None,
) -> str:
    code = secrets.token_urlsafe(32)
    db.session.add(McpOAuthAuthorizationCode(
        code_hash=_sha256_hex(code),
        client_id=client.client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        resource=resource,
        expires_date=datetime.now() + timedelta(seconds=AUTHORIZATION_CODE_TTL_SECONDS),
        is_used=False,
        create_date=datetime.now(),
    ))
    db.session.commit()
    return code


def verify_pkce(code_verifier: str | None, code_challenge: str) -> bool:
    if not code_verifier or not CODE_VERIFIER_PATTERN.match(code_verifier):
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, code_challenge)


def _build_refresh_token(token_id: str, secret: str) -> str:
    return f"{REFRESH_TOKEN_PREFIX}{token_id}.{secret}"


def _parse_refresh_token(raw_token: str | None) -> tuple[str, str] | None:
    if not raw_token or not raw_token.startswith(REFRESH_TOKEN_PREFIX):
        return None
    token_id, _, secret = raw_token[len(REFRESH_TOKEN_PREFIX):].partition(".")
    if not token_id or not secret:
        return None
    return token_id, secret


def _issue_tokens(token_row: McpUserToken, expected_refresh_hash: str | None = None) -> dict[str, Any]:
    """Set fresh access + refresh secrets on the row (rotation) and return the token response.

    With ``expected_refresh_hash`` the rotation is a conditional UPDATE, so only one
    of concurrent refreshes using the same refresh token can win. The rotated-out
    hash is kept in history to recognise its later replay.

    Refresh secrets are 256-bit random values, so plain SHA-256 is sufficient and
    allows looking up the history by hash.
    """
    access_secret = generate_secret()
    refresh_secret = generate_secret()
    now = datetime.now()
    values = {
        "token_prefix": access_secret[:8],
        "token_hash": generate_password_hash(access_secret),
        "expires_date": now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS),
        "refresh_token_hash": _sha256_hex(refresh_secret),
        "refresh_expires_date": now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
        "update_date": now,
    }
    if expected_refresh_hash is None:
        for key, value in values.items():
            setattr(token_row, key, value)
        db.session.add(token_row)
    else:
        updated = (
            McpUserToken.query
            .filter_by(id=token_row.id, refresh_token_hash=expected_refresh_hash, is_revoked=False)
            .update(values, synchronize_session=False)
        )
        if updated != 1:
            db.session.rollback()
            _revoke_token_row_id(token_row.id)
            raise OAuthError("invalid_grant", "Refresh token was already used")
        db.session.add(McpOAuthRefreshTokenHistory(
            token_row_id=token_row.id,
            token_hash=expected_refresh_hash,
            create_date=now,
        ))
    db.session.commit()
    return {
        "access_token": build_plain_mcp_token(token_row.token_id, access_secret),
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "refresh_token": _build_refresh_token(token_row.token_id, refresh_secret),
        "scope": token_row.scope,
    }


def _revoke_row(token_row: McpUserToken) -> None:
    token_row.is_revoked = True
    token_row.update_date = datetime.now()
    db.session.add(token_row)


def _revoke_token_row_id(token_row_id: int | None) -> None:
    if not token_row_id:
        return
    McpUserToken.query.filter_by(id=token_row_id).update(
        {"is_revoked": True, "update_date": datetime.now()},
        synchronize_session=False,
    )
    db.session.commit()


def exchange_authorization_code(
    client: McpOAuthClient,
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
    resource: str | None = None,
) -> dict[str, Any]:
    if not code:
        raise OAuthError("invalid_request", "code is required")
    resource = validate_resource(resource)
    code_row = McpOAuthAuthorizationCode.query.filter_by(code_hash=_sha256_hex(code)).first()
    if code_row is None or code_row.client_id != client.client_id:
        raise OAuthError("invalid_grant", "Invalid authorization code")

    # Consume the code atomically; only one concurrent request can flip is_used.
    # Consumption, token creation and code_row.token_row_id are committed in one
    # transaction, so a concurrent replay waits on the row lock and then always
    # sees token_row_id of the issued token.
    consumed = (
        McpOAuthAuthorizationCode.query
        .filter_by(id=code_row.id, is_used=False)
        .update({"is_used": True}, synchronize_session=False)
    )
    if consumed != 1:
        db.session.commit()
        db.session.refresh(code_row)
        # RFC 6749 4.1.2: code replay -> revoke tokens issued from it.
        _revoke_token_row_id(code_row.token_row_id)
        raise OAuthError("invalid_grant", "Authorization code was already used")

    try:
        if code_row.expires_date < datetime.now():
            raise OAuthError("invalid_grant", "Authorization code expired")
        if redirect_uri is not None and redirect_uri != code_row.redirect_uri:
            raise OAuthError("invalid_grant", "redirect_uri mismatch")
        if not verify_pkce(code_verifier, code_row.code_challenge):
            raise OAuthError("invalid_grant", "PKCE verification failed")
        if resource and code_row.resource and resource != code_row.resource:
            raise OAuthError("invalid_target", "resource mismatch")
    except OAuthError:
        # Failed attempt still burns the code.
        db.session.commit()
        raise

    now = datetime.now()
    token_row = McpUserToken(
        user_id=code_row.user_id,
        token_id=generate_unique_token_id(),
        token_name=f"{client.client_name or 'OAuth client'} (OAuth)"[:128],
        token_prefix="",
        token_hash="",
        scope=code_row.scope,
        is_revoked=False,
        oauth_client_id=client.client_id,
        create_date=now,
        update_date=now,
    )
    db.session.add(token_row)
    db.session.flush()
    code_row.token_row_id = token_row.id
    client.last_used_date = now
    db.session.add(client)
    return _issue_tokens(token_row)


def refresh_access_token(
    client: McpOAuthClient,
    refresh_token: str | None,
    scope: str | None = None,
    resource: str | None = None,
) -> dict[str, Any]:
    validate_resource(resource)
    parsed = _parse_refresh_token(refresh_token)
    if parsed is None:
        raise OAuthError("invalid_grant", "Invalid refresh token")
    token_id, secret = parsed
    token_row = McpUserToken.query.filter_by(token_id=token_id).first()
    if (
        token_row is None
        or token_row.oauth_client_id != client.client_id
        or token_row.is_revoked
        or not token_row.refresh_token_hash
        or (token_row.refresh_expires_date and token_row.refresh_expires_date < datetime.now())
    ):
        raise OAuthError("invalid_grant", "Invalid refresh token")
    secret_hash = _sha256_hex(secret)
    if not hmac.compare_digest(secret_hash, token_row.refresh_token_hash):
        # Replay of an already rotated refresh token (RFC 9700 4.14.2) revokes the grant.
        # Any other secret is just invalid: token_id is part of the access token too,
        # so a wrong secret alone must not be able to revoke someone's grant.
        replayed = McpOAuthRefreshTokenHistory.query.filter_by(
            token_row_id=token_row.id,
            token_hash=secret_hash,
        ).first()
        if replayed is not None:
            _revoke_token_row_id(token_row.id)
        raise OAuthError("invalid_grant", "Invalid refresh token")

    if scope:
        requested = scope.split()
        current = set((token_row.scope or "").split())
        if not set(requested) <= current:
            raise OAuthError("invalid_scope", "Requested scope exceeds the original grant")
        token_row.scope = " ".join(dict.fromkeys(requested))

    client.last_used_date = datetime.now()
    db.session.add(client)
    return _issue_tokens(token_row, expected_refresh_hash=token_row.refresh_token_hash)


def revoke_token(client: McpOAuthClient, raw_token: str | None) -> None:
    """RFC 7009: always succeed, revoke only tokens owned by the client."""
    is_refresh = True
    parsed = _parse_refresh_token(raw_token)
    if parsed is None:
        is_refresh = False
        parsed = parse_plain_mcp_token(raw_token or "")
    if parsed is None:
        return
    token_id, secret = parsed
    token_row = McpUserToken.query.filter_by(token_id=token_id).first()
    if token_row is None or token_row.oauth_client_id != client.client_id or token_row.is_revoked:
        return
    if is_refresh:
        matches = bool(token_row.refresh_token_hash) and hmac.compare_digest(
            _sha256_hex(secret), token_row.refresh_token_hash
        )
    else:
        matches = bool(token_row.token_hash) and check_password_hash(token_row.token_hash, secret)
    if not matches:
        return
    _revoke_row(token_row)
    db.session.commit()
