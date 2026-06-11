"""
API key and admin token validation.

All comparisons use hmac.compare_digest on fixed-length HMAC digests so the
comparison time is independent of key length and match position.  Padding
with null bytes (as done in many naive implementations) leaks the configured
key length via timing because compare_digest runs for max(len_a,len_b) bytes.
The fix: HMAC both values with a stable internal key → both produce 32-byte
digests regardless of input length, eliminating all length side-channels.
"""
import hashlib
import hmac

from core.config import settings

# Internal HMAC key for constant-length digest generation.
# Not a secret — its purpose is solely to normalise input length, not
# to add cryptographic strength beyond what compare_digest already provides.
_CMP_KEY = b"nav-api-compare-v1"


def _digest(value: bytes) -> bytes:
    """Return a 32-byte HMAC-SHA256 digest regardless of input length."""
    return hmac.new(_CMP_KEY, value, hashlib.sha256).digest()


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
    key_d = _digest(key.encode())
    for configured in settings.API_KEYS:
        if hmac.compare_digest(key_d, _digest(configured.encode())):
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

    if not hmac.compare_digest(_digest(token.encode()), _digest(settings.ADMIN_TOKEN.encode())):
        raise PermissionError("Invalid or missing admin token")
    return token
