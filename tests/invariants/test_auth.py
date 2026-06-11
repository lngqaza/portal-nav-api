"""
AUTH invariants — AUTH-01 through AUTH-05.
These tests need no DB or model — they test routing and header parsing only.
"""
import hmac
import pytest


# ── AUTH-01 ──────────────────────────────────────────────────────────────────

def test_auth01_missing_api_key_returns_401(invoke):
    """POST /query without X-API-Key → 401."""
    status, body = invoke("POST", "/query", body={"query": "test"})
    assert status == 401, f"Expected 401, got {status}: {body}"


def test_auth01_wrong_api_key_returns_401(invoke):
    """POST /query with an invalid key → 401."""
    status, body = invoke("POST", "/query", body={"query": "test"}, api_key="bad-key-xyz")
    assert status == 401


def test_auth01_batch_missing_key_returns_401(invoke):
    """POST /query/batch without key → 401."""
    status, body = invoke("POST", "/query/batch", body={"queries": ["test"]})
    assert status == 401


# ── AUTH-02 ──────────────────────────────────────────────────────────────────

def test_auth02_valid_key_not_401(invoke, valid_api_key):
    """POST /query with a valid key never returns 401."""
    status, _ = invoke("POST", "/query", body={"query": "test"}, api_key=valid_api_key)
    assert status != 401, "Valid API key should not produce 401"


# ── AUTH-03 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/admin/hot-paths",
    "/admin/index",
    "/admin/stats",
    "/admin/config",
])
def test_auth03_admin_missing_token_returns_401(invoke, path):
    """GET /admin/* without Authorization → 401."""
    status, body = invoke("GET", path)
    assert status == 401, f"{path} without token should return 401, got {status}"


def test_auth03_admin_wrong_token_returns_401(invoke):
    """GET /admin/stats with wrong bearer token → 401."""
    status, _ = invoke("GET", "/admin/stats", admin_token="wrong-token")
    assert status == 401


# ── AUTH-04 ──────────────────────────────────────────────────────────────────

def test_auth04_api_key_validation_uses_compare_digest():
    """
    validate_api_key uses hmac.compare_digest — not string equality.

    Timing attacks on == can reveal key length and matching prefix byte-by-byte.
    hmac.compare_digest runs in constant time regardless of where bytes differ.
    This test asserts the implementation, not just the observable behaviour.
    """
    import inspect
    from core import auth
    # The constant-time comparison lives in resolve_scope, which
    # validate_api_key delegates to (multi-tenancy refactor).
    source = inspect.getsource(auth.resolve_scope)
    assert "hmac.compare_digest" in source, (
        "resolve_scope must use hmac.compare_digest — not == or 'in'"
    )
    # Also confirm the banned patterns are absent from the auth module source
    full_source = inspect.getsource(auth)
    # Direct token comparison must not appear — hmac.compare_digest replaces it
    assert "token ==" not in full_source, "Timing-unsafe token == found in auth module"
    assert "token !=" not in full_source, "Timing-unsafe token != found in auth module"


def test_auth04_admin_token_validation_uses_compare_digest():
    """validate_admin_token uses hmac.compare_digest — not string equality."""
    import inspect
    from core import auth
    source = inspect.getsource(auth.validate_admin_token)
    assert "hmac.compare_digest" in source, (
        "validate_admin_token must use hmac.compare_digest — not == or !="
    )


def test_auth04_wrong_prefix_keys_all_rejected(invoke):
    """
    Keys that are correct-length prefix-matches of a valid key are rejected.

    A timing-unsafe implementation that short-circuits on byte mismatch
    returns faster for a prefix match than for a completely wrong key.
    This test verifies functional correctness of the constant-time path
    (timing itself cannot be asserted in a unit test, but the result can be).
    """
    from core.config import settings
    if not settings.API_KEYS:
        pytest.skip("No API_KEYS configured")

    first_key = settings.API_KEYS[0]
    if len(first_key) < 4:
        pytest.skip("Key too short to test prefix rejection")

    # A key that shares the first half of the valid key must be rejected
    prefix_key = first_key[: len(first_key) // 2]
    status, _ = invoke("POST", "/query", body={"query": "test"}, api_key=prefix_key)
    assert status == 401, f"Prefix key '{prefix_key}' should be rejected (401), got {status}"


# ── AUTH-05 ──────────────────────────────────────────────────────────────────

def test_auth05_health_no_auth_required(invoke):
    """GET /health requires no authentication."""
    status, body = invoke("GET", "/health")
    assert status == 200
    assert body.get("status") == "ok"


def test_auth05_suggest_no_auth_required(invoke):
    """GET /query/suggest requires no authentication."""
    status, body = invoke("GET", "/query/suggest", params={"q": "test"})
    assert status == 200
    assert isinstance(body, list)
