"""
API key and admin token validation.

All comparisons use hmac.compare_digest so the time taken is independent of
whether the key matches and independent of which byte first differs.  Direct
string equality (==, !=, `in`) leaks key length and match position through
timing and must never be used on secrets.
"""
import hmac

from core.config import settings


def validate_api_key(headers: dict) -> str:
    """
    Validate the X-Api-Key header against every configured key.

    Iterates ALL keys regardless of early match to prevent timing attacks that
    could enumerate valid key prefixes.

    Args:
        headers: lowercase-normalised HTTP headers dict from the Lambda event.

    Returns:
        The key's site scope: list of site_ids, home site first.

    Raises:
        PermissionError: if the key is absent, empty, or does not match any
            configured key.
    """
    scope = resolve_scope(headers.get("x-api-key", ""))
    if scope is None:
        raise PermissionError("Invalid or missing API key")
    return scope


def resolve_scope(key: str):
    """Constant-time lookup of the site scope for an API key.

    Iterates ALL keys regardless of early match to prevent timing attacks.

    Args:
        key: Raw API key string (may be empty).

    Returns:
        List of site_ids (home site first), or None when the key matches nothing.
    """
    if not key:
        return None

    # Compare against every configured key in constant time.
    # hmac.compare_digest requires equal-length bytes; encode both sides so a
    # length mismatch doesn't short-circuit before the byte-by-byte compare.
    scope = None
    key_b = key.encode()
    for configured in settings.API_KEYS:
        # Pad the shorter string to the length of the longer before comparing
        # so the digest comparison itself runs for the same number of bytes.
        cfg_b = configured.encode()
        # Use the longer length to avoid leaking length information.
        max_len = max(len(key_b), len(cfg_b))
        if hmac.compare_digest(
            key_b.ljust(max_len, b"\x00"),
            cfg_b.ljust(max_len, b"\x00"),
        ):
            scope = settings.KEY_SCOPES.get(configured, ["default"])
        # Do NOT break — always iterate all keys.
    return scope


def validate_admin_token(headers: dict) -> str:
    """
    Validate the Authorization: Bearer <token> header.

    Args:
        headers: lowercase-normalised HTTP headers dict from the Lambda event.

    Returns:
        The validated token string.

    Raises:
        PermissionError: if the token is absent, empty, or does not match the
            configured admin token.
    """
    auth = headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token or not settings.ADMIN_TOKEN:
        raise PermissionError("Invalid or missing admin token")

    token_b = token.encode()
    expected_b = settings.ADMIN_TOKEN.encode()
    max_len = max(len(token_b), len(expected_b))
    if not hmac.compare_digest(
        token_b.ljust(max_len, b"\x00"),
        expected_b.ljust(max_len, b"\x00"),
    ):
        raise PermissionError("Invalid or missing admin token")
    return token
