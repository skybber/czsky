from __future__ import annotations

import os
import re
from typing import Any, Callable

ENV_FALSE_VALUES = {"0", "false", "no", "off"}
USER_SUBJECT_PATTERNS = (
    re.compile(r"^(\d+)$"),
    re.compile(r"^u_(\d+)$"),
    re.compile(r"^user:(\d+)$"),
)


def get_access_token():
    import logging

    try:
        from mcp.server.auth.middleware.auth_context import get_access_token as get_token
    except ImportError:
        return None

    try:
        return get_token()
    except Exception as exc:
        logging.getLogger(__name__).error("Failed to get MCP access token: %s", exc)
        return None


def is_env_flag_enabled(name: str, default: bool = True) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in ENV_FALSE_VALUES


def normalize_host_for_url(host: str) -> str:
    normalized = (host or "").strip() or "127.0.0.1"
    if normalized in {"0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return normalized


def build_base_url(host: str, port: int) -> str:
    normalized_host = normalize_host_for_url(host)
    if ":" in normalized_host and not normalized_host.startswith("["):
        normalized_host = f"[{normalized_host}]"
    return f"http://{normalized_host}:{port}"


def verify_db_mcp_token(raw_token: str, *, get_app: Callable[[], Any]) -> dict[str, Any] | None:
    from app.main.usersettings.mcp_token_service import verify_user_mcp_token

    app = get_app()
    with app.app_context():
        return verify_user_mcp_token(raw_token=raw_token)


def parse_positive_user_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        for pattern in USER_SUBJECT_PATTERNS:
            matched = pattern.match(stripped)
            if matched:
                parsed = int(matched.group(1))
                return parsed if parsed > 0 else None
    return None


def extract_user_id_from_access_token(
    access_token: Any,
    *,
    parse_positive_user_id_func: Callable[[Any], int | None],
) -> int | None:
    if not access_token:
        return None

    candidate_values = []
    for key in ("user_id", "sub", "subject", "uid", "client_id"):
        candidate_values.append(getattr(access_token, key, None))

    if hasattr(access_token, "model_dump"):
        token_payload = access_token.model_dump()
        for key in ("user_id", "sub", "subject", "uid", "client_id"):
            candidate_values.append(token_payload.get(key))

    for candidate in candidate_values:
        parsed_user_id = parse_positive_user_id_func(candidate)
        if parsed_user_id is not None:
            return parsed_user_id
    return None


def resolve_wishlist_user_id(
    user_id: int | None = None,
    *,
    get_access_token_func: Callable[[], Any],
    extract_user_id_from_access_token_func: Callable[[Any], int | None],
    parse_positive_user_id_func: Callable[[Any], int | None],
) -> int:
    if user_id is not None and user_id <= 0:
        raise ValueError("user_id must be positive")

    access_token = get_access_token_func()
    token_user_id = extract_user_id_from_access_token_func(access_token)
    if token_user_id is not None:
        if user_id is not None and user_id != token_user_id:
            raise PermissionError("Provided user_id does not match authenticated token subject")
        return token_user_id

    if user_id is not None:
        return user_id

    env_user_id = parse_positive_user_id_func(os.getenv("MCP_USER_ID"))
    if env_user_id is not None:
        return env_user_id

    raise PermissionError(
        "Missing user identity for wishlist tools. "
        "Provide a token with subject claims or pass user_id in stub mode."
    )


def require_scope_if_available(
    required_scope: str,
    *,
    get_access_token_func: Callable[[], Any],
) -> None:
    access_token = get_access_token_func()
    if access_token is None:
        return

    token_scopes = getattr(access_token, "scopes", None)
    if token_scopes is None and hasattr(access_token, "model_dump"):
        token_scopes = access_token.model_dump().get("scopes")
    if token_scopes is None:
        return

    if isinstance(token_scopes, str):
        token_scopes = token_scopes.split()

    if required_scope not in token_scopes:
        raise PermissionError(f"Missing required scope '{required_scope}'")


def build_mcp_auth_kwargs(
    mcp_host: str,
    mcp_port: int,
    *,
    is_env_flag_enabled_func: Callable[[str, bool], bool],
    build_base_url_func: Callable[[str, int], str],
    verify_db_mcp_token_func: Callable[[str], dict[str, Any] | None],
    parse_positive_user_id_func: Callable[[Any], int | None],
) -> dict[str, Any]:
    if not is_env_flag_enabled_func("MCP_ENABLE_TOKEN_AUTH", True):
        return {}

    try:
        from mcp.server.auth.provider import AccessToken
        from mcp.server.auth.settings import AuthSettings
    except ImportError:
        return {}

    class CzskyAccessToken(AccessToken):
        user_id: int
        token_id: str | None = None

    class CzskyTokenVerifier:
        async def verify_token(self, token: str) -> AccessToken | None:
            try:
                verified_token = verify_db_mcp_token_func(token)
            except Exception:
                return None

            if not verified_token:
                return None

            user_id = parse_positive_user_id_func(verified_token.get("user_id"))
            if user_id is None:
                return None

            scopes = verified_token.get("scopes") or []
            if isinstance(scopes, str):
                scopes = scopes.split()
            else:
                scopes = [scope for scope in scopes if isinstance(scope, str) and scope]

            token_id = verified_token.get("token_id")
            return CzskyAccessToken(
                token=token,
                client_id=f"user:{user_id}",
                scopes=scopes,
                user_id=user_id,
                token_id=str(token_id) if token_id is not None else None,
            )

    base_url = build_base_url_func(mcp_host, mcp_port)
    issuer_url = os.getenv("MCP_AUTH_ISSUER_URL") or base_url
    resource_server_url = os.getenv("MCP_AUTH_RESOURCE_SERVER_URL") or f"{base_url}/mcp"

    return {
        "token_verifier": CzskyTokenVerifier(),
        "auth": AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_server_url,
        ),
    }
