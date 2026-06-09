"""
AUTH invariants — AUTH-01 through AUTH-05.
These tests need no DB or model — they test routing and header parsing only.
"""
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
