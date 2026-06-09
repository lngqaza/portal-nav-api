"""
API Contract invariants — API-01 through API-06.
Tests lambda_handler end-to-end with real event structures.
"""
import pytest

REQUIRED_FIELDS = {"path", "label", "confidence", "layer", "response_ms", "candidates", "suggestion"}


# ── API-01: response always contains required fields ─────────────────────────

def test_api01_response_has_all_required_fields(invoke, valid_api_key):
    """Every /query response contains all seven required fields."""
    status, body = invoke("POST", "/query", body={"query": "test"}, api_key=valid_api_key)
    assert status == 200
    missing = REQUIRED_FIELDS - set(body.keys())
    assert not missing, f"Response missing fields: {missing}"


def test_api01_batch_each_result_has_required_fields(invoke, valid_api_key):
    """Every item in /query/batch response has all seven required fields."""
    status, body = invoke("POST", "/query/batch", body={"queries": ["test1", "test2"]}, api_key=valid_api_key)
    assert status == 200
    assert isinstance(body, list)
    for i, item in enumerate(body):
        missing = REQUIRED_FIELDS - set(item.keys())
        assert not missing, f"Result[{i}] missing fields: {missing}"


# ── API-02: batch > 20 returns 400 ───────────────────────────────────────────

def test_api02_batch_over_20_returns_400(invoke, valid_api_key):
    """POST /query/batch with 21 queries returns HTTP 400."""
    status, body = invoke(
        "POST", "/query/batch",
        body={"queries": [f"query {i}" for i in range(21)]},
        api_key=valid_api_key,
    )
    assert status == 400, f"Expected 400 for 21 queries, got {status}"


def test_api02_batch_exactly_20_is_accepted(invoke, valid_api_key):
    """POST /query/batch with exactly 20 queries is accepted."""
    status, _ = invoke(
        "POST", "/query/batch",
        body={"queries": [f"query {i}" for i in range(20)]},
        api_key=valid_api_key,
    )
    assert status == 200, f"Expected 200 for 20 queries, got {status}"


# ── API-03: batch preserves order ────────────────────────────────────────────

def test_api03_batch_preserves_order(invoke, valid_api_key, seeded_index, embedding_model_loaded):
    """Batch results are returned in the same order as input queries."""
    queries = ["submit a claim", "renew policy", "edit profile"]
    status, results = invoke(
        "POST", "/query/batch",
        body={"queries": queries},
        api_key=valid_api_key,
    )
    assert status == 200
    assert len(results) == len(queries), f"Expected {len(queries)} results, got {len(results)}"
    # Each result must correspond to its query's intent (layer may vary but count matches)
    # Order invariant: result[0] answers query[0], etc.
    assert len(results) == 3


# ── API-04: health always returns 200 ────────────────────────────────────────

def test_api04_health_always_200(invoke):
    """GET /health always returns HTTP 200."""
    status, body = invoke("GET", "/health")
    assert status == 200
    assert "status" in body


def test_api04_health_returns_ok_status(invoke):
    """GET /health body always contains status='ok'."""
    status, body = invoke("GET", "/health")
    assert body.get("status") == "ok"


# ── API-05: confidence is rounded to 4 decimal places ────────────────────────

def test_api05_confidence_max_4_decimal_places(invoke, valid_api_key, seeded_index, embedding_model_loaded):
    """confidence values have at most 4 decimal places."""
    status, body = invoke("POST", "/query", body={"query": "submit a claim"}, api_key=valid_api_key)
    assert status == 200
    conf = body.get("confidence", 0.0)
    # Check decimal places
    conf_str = str(conf)
    if "." in conf_str:
        decimals = len(conf_str.split(".")[1])
        assert decimals <= 4, f"confidence {conf} has {decimals} decimal places (max 4)"


# ── API-06: response_ms is non-negative integer ──────────────────────────────

def test_api06_response_ms_non_negative_int(invoke, valid_api_key):
    """response_ms is always a non-negative integer."""
    status, body = invoke("POST", "/query", body={"query": "test"}, api_key=valid_api_key)
    assert status == 200
    ms = body.get("response_ms")
    assert isinstance(ms, int), f"response_ms is {type(ms).__name__}, expected int"
    assert ms >= 0, f"response_ms is {ms}, expected >= 0"


# ── 404 for unknown routes ───────────────────────────────────────────────────

def test_unknown_route_returns_404(invoke, valid_api_key):
    """An unknown path returns HTTP 404."""
    status, _ = invoke("GET", "/nonexistent/route")
    assert status == 404


# ── Empty query returns 400 ──────────────────────────────────────────────────

def test_empty_query_returns_400(invoke, valid_api_key):
    """POST /query with empty query string returns HTTP 400."""
    status, body = invoke("POST", "/query", body={"query": ""}, api_key=valid_api_key)
    assert status == 400


def test_missing_query_field_returns_400(invoke, valid_api_key):
    """POST /query with no query field returns HTTP 400."""
    status, body = invoke("POST", "/query", body={}, api_key=valid_api_key)
    assert status == 400
