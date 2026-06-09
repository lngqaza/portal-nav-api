"""
Fixture Model for portal-nav-api invariant tests.

Fixture dependency graph:
    db_url
        └── raw_conn
                └── clean_db
                        ├── seeded_index      (3 pages in nav_index with embeddings)
                        ├── seeded_hot_paths  (3 rows in nav_hot_paths)
                        └── seeded_all        (both above)

    settings_override          (context-manager fixture to patch Settings)
    lambda_event_factory       (builds API Gateway proxy events)
    invoke                     (calls lambda_handler and returns parsed body)
    embedding_model_loaded     (asserts ONNX embedding session is initialised)
"""

import json
import os
import sys
import uuid
import pytest
import psycopg2

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────
# Database fixtures
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_url():
    """
    Resolve test database URL.
    Uses NAV_TEST_DATABASE_URL env var if set, otherwise falls back to
    the service DATABASE_URL — tests run against the real DB but in
    isolated tables cleared by clean_db.
    """
    url = os.environ.get("NAV_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL set — skipping DB-dependent tests")
    # Normalise asyncpg URLs
    for old, new in (("postgresql+asyncpg://", "postgresql://"), ("postgres+asyncpg://", "postgresql://")):
        if url.startswith(old):
            url = new + url[len(old):]
    return url


@pytest.fixture(scope="session")
def db_reachable(db_url):
    """Session-scoped check: skip all DB tests if the host is unreachable."""
    import socket
    host = db_url.split("@")[-1].split(":")[0].split("/")[0]
    s = socket.socket()
    s.settimeout(4)
    try:
        s.connect((host, 5432))
        s.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="function")
def raw_conn(db_url, db_reachable):
    """Raw psycopg2 connection — rolled back after each test."""
    if not db_reachable:
        pytest.skip("RDS port 5432 unreachable from this network — run in CI or with VPN")
    conn = psycopg2.connect(dsn=db_url)
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(scope="function")
def clean_db(raw_conn):
    """
    Truncate all nav_ tables before the test, yield the connection,
    then roll back after — each test starts with a clean slate.
    """
    with raw_conn.cursor() as cur:
        cur.execute(
            "TRUNCATE nav_hot_paths, nav_index, nav_query_log, nav_config RESTART IDENTITY CASCADE"
        )
    raw_conn.commit()
    yield raw_conn
    raw_conn.rollback()


@pytest.fixture(scope="function")
def seeded_index(clean_db):
    """
    nav_index pre-populated with three pages.
    Embeddings are synthetic unit vectors (not real ONNX output).
    """
    import numpy as np

    pages = [
        ("/claims/submit",  "Submit a Claim",   "File and submit insurance claims online",    ["claims", "forms"]),
        ("/policy/renew",   "Renew My Policy",  "Renew or update your existing policy",       ["policy", "renewal"]),
        ("/account/profile","Edit Profile",     "Update your personal details and contact",   ["account", "settings"]),
    ]

    def _unit_vec(seed: int) -> str:
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(384).astype(np.float32)
        v /= np.linalg.norm(v)
        return "[" + ",".join(f"{x:.6f}" for x in v.tolist()) + "]"

    with clean_db.cursor() as cur:
        for i, (path, label, desc, tags) in enumerate(pages):
            vec = _unit_vec(i)
            cur.execute(
                """
                INSERT INTO nav_index (path, label, description, tags, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                ON CONFLICT (path) DO NOTHING
                """,
                (path, label, desc, tags, vec),
            )
    clean_db.commit()
    return {"pages": pages, "conn": clean_db}


@pytest.fixture(scope="function")
def seeded_hot_paths(clean_db):
    """
    nav_hot_paths with three rows at varying hit counts.
    Row 0: high hits, not pinned.
    Row 1: zero hits, pinned.
    Row 2: low hits, old last_hit_at (stale).
    """
    rows = [
        ("high-hit",  "/reports/summary", "Reports Summary",      ["reporting"], 150, False),
        ("pinned",    "/admin/dashboard",  "Admin Dashboard",      ["admin"],     0,   True),
        ("stale",     "/help/faq",         "Help & FAQ",           ["help"],      3,   False),
    ]
    with clean_db.cursor() as cur:
        for tag, path, label, aliases, hits, pinned in rows:
            cur.execute(
                """
                INSERT INTO nav_hot_paths (path, label, aliases, hit_count, pinned, last_hit_at)
                VALUES (%s, %s, %s, %s, %s,
                    CASE WHEN %s = 'stale' THEN now() - interval '60 days' ELSE now() END)
                """,
                (path, label, aliases, hits, pinned, tag),
            )
    clean_db.commit()
    return {"rows": rows, "conn": clean_db}


@pytest.fixture(scope="function")
def seeded_all(seeded_index, seeded_hot_paths):
    """Both nav_index and nav_hot_paths populated."""
    return {"index": seeded_index, "hot_paths": seeded_hot_paths}


# ─────────────────────────────────────────────
# Settings override fixture
# ─────────────────────────────────────────────

@pytest.fixture
def settings_override():
    """
    Context manager that temporarily patches core.config.settings attributes.

    Usage:
        with settings_override(HOT_PATH_THRESHOLD=0.9):
            ...
    """
    from core.config import settings

    class _Override:
        def __init__(self, **kwargs):
            self._kwargs = kwargs
            self._original = {}

        def __enter__(self):
            for k, v in self._kwargs.items():
                self._original[k] = getattr(settings, k)
                setattr(settings, k, v)
            return settings

        def __exit__(self, *_):
            for k, v in self._original.items():
                setattr(settings, k, v)

    return _Override


# ─────────────────────────────────────────────
# Lambda invocation fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def lambda_event_factory():
    """
    Factory that builds minimal API Gateway HTTP API v2 proxy events.

    Usage:
        event = lambda_event_factory("POST", "/query", body={"query": "submit claim"}, api_key="k")
    """
    def _make(method: str, path: str, body=None, headers=None, params=None):
        h = {"content-type": "application/json"}
        if headers:
            h.update({k.lower(): v for k, v in headers.items()})
        return {
            "version": "2.0",
            "rawPath": path,
            "requestContext": {"http": {"method": method.upper(), "path": path}},
            "headers": h,
            "queryStringParameters": params or {},
            "body": json.dumps(body) if body is not None else None,
            "isBase64Encoded": False,
        }

    return _make


@pytest.fixture
def invoke(lambda_event_factory, db_reachable):
    """
    Invoke lambda_handler and return (status_code, parsed_body).
    Skips if DB is required and unreachable (detects 500 from uninitialised pool).

    Usage:
        status, body = invoke("POST", "/query", body={"query": "..."}, api_key="k")
    """
    import handler as h_module  # Import after sys.path is set

    # Re-init pool now that DB URL is set in env
    if db_reachable:
        from core.db import init_pool
        init_pool()

    def _invoke(method: str, path: str, body=None, api_key=None, admin_token=None,
                params=None, require_db: bool = False):
        if require_db and not db_reachable:
            pytest.skip("RDS unreachable from this network")

        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        if admin_token:
            headers["authorization"] = f"Bearer {admin_token}"

        event = lambda_event_factory(method, path, body=body, headers=headers, params=params)
        result = h_module.lambda_handler(event, None)
        status = result["statusCode"]
        raw_body = result.get("body", "{}")
        try:
            parsed = json.loads(raw_body)
        except Exception:
            parsed = raw_body

        # Auto-skip if DB pool failure causes unexpected 500 on a non-auth path
        if status == 500 and not db_reachable and path not in ("/health",):
            pytest.skip(f"500 on {path} — DB pool not initialised (RDS unreachable)")

        return status, parsed

    return _invoke


# ─────────────────────────────────────────────
# Model fixtures
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def embedding_model_loaded():
    """Assert embedding ONNX model is loaded; skip if absent."""
    from services.embedding import _session, load_model
    if _session is None:
        load_model()
    from services.embedding import _session as s
    if s is None:
        pytest.skip("Embedding ONNX model not available — skipping embedding tests")
    return s


@pytest.fixture(scope="session")
def reranker_model_loaded():
    """Assert reranker ONNX model is loaded; skip if absent."""
    from services.reranker import _session, load_reranker
    if _session is None:
        load_reranker()
    from services.reranker import _session as s
    if s is None:
        pytest.skip("Reranker ONNX model not available — skipping reranker tests")
    return s


# ─────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def valid_api_key():
    from core.config import settings
    if not settings.API_KEYS:
        return "test-key-fixture"
    return settings.API_KEYS[0]


@pytest.fixture(scope="session")
def valid_admin_token():
    from core.config import settings
    return settings.ADMIN_TOKEN or "test-admin-fixture"
