from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import McpUserToken

TOKEN_PREFIX = "czmcp_"
DEFAULT_SCOPE = "wishlist:read"


def normalize_scope(scope: str | None) -> str:
    if not scope:
        return DEFAULT_SCOPE
    parts = [part.strip() for part in scope.split(" ") if part.strip()]
    if not parts:
        return DEFAULT_SCOPE
    return " ".join(dict.fromkeys(parts))


def normalize_token_name(token_name: str) -> str:
    normalized = (token_name or "").strip()
    if not normalized:
        raise ValueError("token_name must not be empty")
    if len(normalized) > 128:
        raise ValueError("token_name must be at most 128 characters")
    return normalized


def build_plain_mcp_token(token_id: str, secret: str) -> str:
    return f"{TOKEN_PREFIX}{token_id}.{secret}"


def parse_plain_mcp_token(raw_token: str) -> tuple[str, str] | None:
    if not raw_token:
        return None
    token_value = raw_token.strip()
    if not token_value.startswith(TOKEN_PREFIX):
        return None

    payload = token_value[len(TOKEN_PREFIX):]
    if "." not in payload:
        return None

    token_id, secret = payload.split(".", 1)
    if not token_id or not secret:
        return None
    return token_id, secret


def _generate_token_id() -> str:
    return secrets.token_hex(12)


def _generate_secret() -> str:
    return secrets.token_urlsafe(32)


def _generate_unique_token_id() -> str:
    for _ in range(8):
        token_id = _generate_token_id()
        exists = McpUserToken.query.filter_by(token_id=token_id).first()
        if not exists:
            return token_id
    raise RuntimeError("Failed to generate unique token id")


def create_user_mcp_token(
    user_id: int,
    token_name: str,
    scope: str | None = None,
    expires_in_days: int | None = 365,
) -> tuple[McpUserToken, str]:
    if user_id <= 0:
        raise ValueError("user_id must be positive")

    normalized_name = normalize_token_name(token_name)
    normalized_scope = normalize_scope(scope)

    if expires_in_days is not None:
        if expires_in_days < 1:
            raise ValueError("expires_in_days must be >= 1")
        expires_date = datetime.now() + timedelta(days=expires_in_days)
    else:
        expires_date = None

    token_id = _generate_unique_token_id()
    secret = _generate_secret()
    plain_token = build_plain_mcp_token(token_id, secret)

    token_row = McpUserToken(
        user_id=user_id,
        token_id=token_id,
        token_name=normalized_name,
        token_prefix=secret[:8],
        token_hash=generate_password_hash(secret),
        scope=normalized_scope,
        expires_date=expires_date,
        is_revoked=False,
        create_date=datetime.now(),
        update_date=datetime.now(),
    )

    db.session.add(token_row)
    db.session.commit()
    return token_row, plain_token


def list_user_mcp_tokens(user_id: int) -> list[McpUserToken]:
    return (
        McpUserToken.query
        .filter_by(user_id=user_id)
        .order_by(McpUserToken.create_date.desc())
        .all()
    )


def revoke_user_mcp_token(user_id: int, token_row_id: int) -> bool:
    token_row = McpUserToken.query.filter_by(id=token_row_id, user_id=user_id).first()
    if token_row is None or token_row.is_revoked:
        return False

    token_row.is_revoked = True
    token_row.update_date = datetime.now()
    db.session.add(token_row)
    db.session.commit()
    return True


def verify_user_mcp_token(
    raw_token: str,
    required_scope: str | None = None,
) -> dict[str, Any] | None:
    parsed = parse_plain_mcp_token(raw_token)
    if parsed is None:
        return None

    token_id, secret = parsed
    token_row = McpUserToken.query.filter_by(token_id=token_id).first()
    if token_row is None:
        return None
    if token_row.is_revoked:
        return None
    if token_row.expires_date and token_row.expires_date < datetime.now():
        return None
    if not check_password_hash(token_row.token_hash, secret):
        return None

    token_scopes = set((token_row.scope or "").split())
    if required_scope and required_scope not in token_scopes:
        return None

    token_row.last_used_date = datetime.now()
    token_row.update_date = datetime.now()
    db.session.add(token_row)
    db.session.commit()

    return {
        "user_id": token_row.user_id,
        "scopes": sorted(token_scopes),
        "token_row_id": token_row.id,
        "token_id": token_row.token_id,
    }
