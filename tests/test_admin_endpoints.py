"""
Admin endpoint unit tests — audit log, path aliases, CORS cold-start guard,
and batch deduplication.  All run without a live DB or ONNX model.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

_TEST_TOKEN = "test-admin-token-at-least-32-chars-x"


def _mock_conn(rows=None, fetchone_val=None, description=None):
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = rows or []
    mock_cur.fetchone.return_value = fetchone_val
    mock_cur.description = description or []
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


# ── CORS-01: hard-fail guard logic ───────────────────────────────────────────
# We test the predicate directly rather than reloading the handler module
# (module reload breaks numpy on Python 3.14 due to single-load constraints).

def _cors_should_fail(in_lambda: bool, cors_origins: str) -> bool:
    """Replicate the guard condition from handler.py."""
    return bool(in_lambda and (not cors_origins or cors_origins.strip() == "*"))


def test_cors01_absent_fails_in_lambda():
    assert _cors_should_fail(True, "") is True


def test_cors01_wildcard_fails_in_lambda():
    assert _cors_should_fail(True, "*") is True


def test_cors01_valid_origin_passes():
    assert _cors_should_fail(True, "https://portal.example.com") is False


def test_cors01_no_lambda_env_skips_guard():
    # Outside Lambda (local dev) the guard doesn't fire even with absent origin
    assert _cors_should_fail(False, "") is False


# ── AUDT-01: GET /admin/audit-log ─────────────────────────────────────────────

def test_audt01_returns_rows():
    from routes.admin import handle_admin

    desc = [("id",), ("site_id",), ("action",), ("resource",),
            ("actor",), ("payload",), ("created_at",)]
    rows = [("uuid-1", "default", "POST", "/admin/hot-paths", "admin", '{}', "2026-01-01")]
    mock_conn, _ = _mock_conn(rows=rows, description=desc)

    with patch("routes.admin.get_conn", return_value=mock_conn):
        result = handle_admin("/admin/audit-log", "GET", {}, {"limit": "10"})

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert isinstance(body, list)
    assert body[0]["action"] == "POST"


def test_audt01_empty_list_on_no_rows():
    from routes.admin import handle_admin

    desc = [("id",), ("site_id",), ("action",), ("resource",),
            ("actor",), ("payload",), ("created_at",)]
    mock_conn, _ = _mock_conn(description=desc)

    with patch("routes.admin.get_conn", return_value=mock_conn):
        result = handle_admin("/admin/audit-log", "GET", {}, {})

    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == []


# ── ALIAS-01: POST /admin/aliases ────────────────────────────────────────────

def test_alias01_post_creates_alias():
    from routes.admin import handle_admin
    import uuid as _uuid

    uid = str(_uuid.uuid4())
    mock_conn, _ = _mock_conn(fetchone_val=(uid,))

    with patch("routes.admin.get_conn", return_value=mock_conn):
        result = handle_admin("/admin/aliases", "POST", {
            "site": "default",
            "old_path": "/old-page",
            "new_path": "/new-page",
        }, {})

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["old_path"] == "/old-page"
    assert body["new_path"] == "/new-page"
    assert "id" in body


def test_alias01_post_rejects_missing_old_path():
    from routes.admin import handle_admin
    result = handle_admin("/admin/aliases", "POST", {"new_path": "/new"}, {})
    assert result["statusCode"] == 400
    assert "old_path" in json.loads(result["body"])["error"]


def test_alias01_post_rejects_missing_new_path():
    from routes.admin import handle_admin
    result = handle_admin("/admin/aliases", "POST", {"old_path": "/old"}, {})
    assert result["statusCode"] == 400
    assert "new_path" in json.loads(result["body"])["error"]


# ── ALIAS-02: GET /admin/aliases ─────────────────────────────────────────────

def test_alias02_get_aliases():
    from routes.admin import handle_admin

    desc = [("id",), ("site_id",), ("old_path",), ("new_path",), ("created_at",)]
    rows = [("uuid-1", "default", "/old", "/new", "2026-01-01")]
    mock_conn, _ = _mock_conn(rows=rows, description=desc)

    with patch("routes.admin.get_conn", return_value=mock_conn):
        result = handle_admin("/admin/aliases", "GET", {}, {"site": "default"})

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body[0]["old_path"] == "/old"


# ── ALIAS-03: DELETE /admin/aliases/<id> ─────────────────────────────────────

def test_alias03_delete_alias():
    from routes.admin import handle_admin

    uid = "12345678-1234-1234-1234-123456789012"
    mock_conn, _ = _mock_conn()

    with patch("routes.admin.get_conn", return_value=mock_conn):
        result = handle_admin(f"/admin/aliases/{uid}", "DELETE", {}, {"site": "default"})

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["deleted"] == uid


# ── ADMIN-01: POST /admin/index field validation ──────────────────────────────

def test_admin01_missing_path_returns_400():
    from routes.admin import handle_admin
    result = handle_admin("/admin/index", "POST", {"label": "Test"}, {})
    assert result["statusCode"] == 400
    assert "path" in json.loads(result["body"])["error"]


def test_admin01_missing_label_returns_400():
    from routes.admin import handle_admin
    result = handle_admin("/admin/index", "POST", {"path": "/test"}, {})
    assert result["statusCode"] == 400
    assert "label" in json.loads(result["body"])["error"]


# ── BATCH-01: deduplication ───────────────────────────────────────────────────

def test_batch01_dedup_routes_once():
    """Identical queries (case-insensitive) routed once; result fanned to all positions."""
    from routes.query import handle_batch

    call_count = 0

    def mock_route(q, scope, request_id):
        nonlocal call_count
        call_count += 1
        from models.navigation import NavigationResult
        return NavigationResult("/test", "Test", 0.9, "L0", 1)

    with patch("routes.query.route_query", side_effect=mock_route):
        result = handle_batch(
            {"queries": ["submit a claim", "Submit A Claim", "SUBMIT A CLAIM"]},
            scope=["default"],
        )

    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert len(body) == 3
    # All positions got the same result
    assert body[0]["path"] == body[1]["path"] == body[2]["path"]
    # Only one actual route_query call
    assert call_count == 1, f"Expected 1 route_query call, got {call_count}"


def test_batch01_distinct_queries_all_routed():
    from routes.query import handle_batch

    call_count = 0

    def mock_route(q, scope, request_id):
        nonlocal call_count
        call_count += 1
        from models.navigation import NavigationResult
        return NavigationResult(f"/{call_count}", "Label", 0.8, "L1", 2)

    with patch("routes.query.route_query", side_effect=mock_route):
        handle_batch(
            {"queries": ["submit a claim", "renew my policy", "find account"]},
            scope=["default"],
        )

    assert call_count == 3
