"""
ROUTE invariants — ROUTE-01 through ROUTE-09.
Tests the 3-layer cascade properties.
"""
import pytest
from unittest.mock import patch, MagicMock
from models.navigation import HotPathResult, EmbeddingResult, NavigationResult

VALID_LAYERS = {"L0", "L1", "L2", "L3", "L4", "MISS"}


# ── ROUTE-01: route_query never raises ────────────────────────────────────────

def test_route01_never_raises_on_empty_query(clean_db):
    """route_query('') returns a NavigationResult — never raises."""
    from services.query_router import route_query
    result = route_query("")
    assert isinstance(result, NavigationResult)


def test_route01_never_raises_on_long_query(clean_db):
    """route_query(very long string) returns NavigationResult — never raises."""
    from services.query_router import route_query
    result = route_query("x" * 10000)
    assert isinstance(result, NavigationResult)


def test_route01_never_raises_on_unicode(clean_db):
    """route_query(unicode) returns NavigationResult — never raises."""
    from services.query_router import route_query
    result = route_query("كيف أقدم مطالبة؟")  # Arabic
    assert isinstance(result, NavigationResult)


# ── ROUTE-02: layer is always in VALID_LAYERS ─────────────────────────────────

@pytest.mark.parametrize("query", ["submit claim", "renew", "xyz123abc", ""])
def test_route02_layer_always_valid(query, clean_db):
    from services.query_router import route_query
    result = route_query(query)
    assert result.layer in VALID_LAYERS, f"Invalid layer: {result.layer!r}"


# ── ROUTE-03: L1 not called when L0 hits ──────────────────────────────────────

def test_route03_l1_not_called_on_l0_hit():
    """When L0 returns a result, services.embedding.search is never called."""
    from services.query_router import route_query
    mock_result = HotPathResult(path="/claims/submit", label="Submit Claim", confidence=0.9, hit_count=10)

    with patch("services.query_router.hp.lookup", return_value=mock_result) as mock_l0, \
         patch("services.query_router.emb.search") as mock_l1:
        result = route_query("submit a claim")

    assert result.layer == "L0"
    mock_l1.assert_not_called()


# ── ROUTE-04: L2 not called when L1 confidence ≥ threshold ────────────────────

def test_route04_l2_not_called_on_l1_confident_hit(settings_override):
    from services.query_router import route_query
    candidates = [EmbeddingResult(path="/p", label="P", description="", score=0.9)]

    with settings_override(L1_THRESHOLD=0.65), \
         patch("services.query_router.hp.lookup", return_value=None), \
         patch("services.query_router.emb.search", return_value=candidates), \
         patch("services.query_router.rer.rerank") as mock_l2:
        result = route_query("test")

    assert result.layer == "L1"
    mock_l2.assert_not_called()


# ── ROUTE-05: L2 not called when L1 returns zero candidates ──────────────────

def test_route05_l2_not_called_when_no_l1_candidates():
    from services.query_router import route_query

    with patch("services.query_router.hp.lookup", return_value=None), \
         patch("services.query_router.emb.search", return_value=[]), \
         patch("services.query_router.rer.rerank") as mock_l2:
        result = route_query("test")

    assert result.layer == "MISS"
    mock_l2.assert_not_called()


# ── ROUTE-06: MISS has path=None and confidence=0.0 ──────────────────────────

def test_route06_miss_has_null_path_zero_confidence():
    from services.query_router import route_query

    with patch("services.query_router.hp.lookup", return_value=None), \
         patch("services.query_router.emb.search", return_value=[]):
        result = route_query("xyzzy_no_match_12345")

    assert result.layer == "MISS"
    assert result.path is None
    assert result.confidence == 0.0


# ── ROUTE-07: non-MISS has non-empty path and label ──────────────────────────

def test_route07_non_miss_has_path_and_label(settings_override):
    from services.query_router import route_query
    candidates = [EmbeddingResult(path="/x", label="X Label", description="", score=0.8)]

    with settings_override(L1_THRESHOLD=0.65), \
         patch("services.query_router.hp.lookup", return_value=None), \
         patch("services.query_router.emb.search", return_value=candidates):
        result = route_query("test")

    assert result.layer != "MISS"
    assert result.path and len(result.path) > 0
    assert result.label and len(result.label) > 0


# ── ROUTE-08: response_ms is non-negative int ─────────────────────────────────

def test_route08_response_ms_non_negative(clean_db):
    from services.query_router import route_query
    result = route_query("test")
    assert isinstance(result.response_ms, int)
    assert result.response_ms >= 0


# ── ROUTE-09: every query is logged exactly once ─────────────────────────────

def test_route09_every_query_logged_once(clean_db):
    from services.query_router import route_query

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_query_log")
        before = cur.fetchone()[0]

    route_query("unique-test-query-for-logging")
    clean_db.commit()  # ensure visible

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_query_log WHERE raw_query = %s", ("unique-test-query-for-logging",))
        count = cur.fetchone()[0]

    assert count == 1, f"Expected 1 log entry, found {count}"


# ── ROUTE-10: PII is scrubbed from raw_query before DB insert ─────────────────

@pytest.mark.parametrize("raw,expected_absent", [
    ("my id is 8501015009087", "8501015009087"),          # SA ID number
    ("email me at user@example.com please", "user@example.com"),
    ("call me on +27 82 123 4567", "+27 82 123 4567"),
    ("card 4111 1111 1111 1111 please", "4111 1111 1111 1111"),
])
def test_route10_pii_scrubbed_before_db(raw, expected_absent):
    """PII patterns in raw_query are replaced before being written to nav_query_log."""
    from services.query_router import _scrub
    scrubbed = _scrub(raw)
    assert expected_absent not in scrubbed, (
        f"PII not scrubbed — '{expected_absent}' still present in: {scrubbed!r}"
    )
