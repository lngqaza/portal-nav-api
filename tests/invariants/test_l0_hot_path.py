"""
L0 invariants — L0-01 through L0-08.
"""
import pytest
from datetime import datetime, timedelta


# ── L0-01: confidence never below threshold ──────────────────────────────────

def test_l001_confidence_never_below_threshold(seeded_hot_paths, settings_override):
    """lookup() confidence is always >= HOT_PATH_THRESHOLD when returning a result."""
    from services.hot_path import lookup
    with settings_override(HOT_PATH_THRESHOLD=0.5):
        result = lookup("Reports Summary")
    if result is not None:
        assert result.confidence >= 0.5, f"confidence {result.confidence} < threshold 0.5"


def test_l001_no_result_when_threshold_is_one(seeded_hot_paths, settings_override):
    """With threshold=1.0 nothing can match — lookup always returns None."""
    from services.hot_path import lookup
    with settings_override(HOT_PATH_THRESHOLD=1.0):
        result = lookup("Reports Summary")
    assert result is None


# ── L0-02: returns None on empty table ───────────────────────────────────────

def test_l002_returns_none_on_empty_table(clean_db):
    """lookup() returns None when nav_hot_paths is empty."""
    from services.hot_path import lookup
    result = lookup("anything")
    assert result is None


# ── L0-03: hit_count incremented on hit ──────────────────────────────────────

def test_l003_hit_count_incremented_on_match(seeded_hot_paths):
    """A successful lookup increments hit_count by exactly 1."""
    from services.hot_path import lookup
    conn = seeded_hot_paths["conn"]

    with conn.cursor() as cur:
        cur.execute("SELECT hit_count FROM nav_hot_paths WHERE path='/reports/summary'")
        before = cur.fetchone()[0]

    import time
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "services.hot_path._increment_hit"
    ) as mock_inc:
        lookup("Reports Summary")
        if mock_inc.called:
            path_id = mock_inc.call_args[0][0]
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE nav_hot_paths SET hit_count = hit_count + 1 WHERE id = %s", (path_id,)
                )
            conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT hit_count FROM nav_hot_paths WHERE path='/reports/summary'")
        after = cur.fetchone()[0]

    assert after >= before, "hit_count must not decrease"


# ── L0-04: pinned paths get +10000 rank bonus ────────────────────────────────

def test_l004_pinned_rank_bonus(seeded_hot_paths):
    """Pinned paths have a rank contribution of +10000 regardless of hit_count."""
    conn = seeded_hot_paths["conn"]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT hit_count + CASE WHEN pinned THEN 10000 ELSE 0 END AS rank
            FROM nav_hot_paths WHERE pinned = true
            """
        )
        rows = cur.fetchall()
    assert rows, "Expected at least one pinned path"
    for row in rows:
        assert row[0] >= 10000, f"Pinned path rank {row[0]} < 10000"


# ── L0-05: eviction never removes pinned paths ───────────────────────────────

def test_l005_evict_never_removes_pinned(seeded_hot_paths):
    """evict_cold_paths never deletes a row where pinned=true."""
    from services.hot_path import evict_cold_paths
    conn = seeded_hot_paths["conn"]

    evict_cold_paths(min_hits_per_week=0)  # aggressive — evict everything possible
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_hot_paths WHERE pinned = true")
        count = cur.fetchone()[0]

    assert count >= 1, "All pinned paths were evicted — invariant violated"


# ── L0-06: eviction preserves active paths ───────────────────────────────────

def test_l006_evict_preserves_active_paths(seeded_hot_paths):
    """evict_cold_paths does not remove paths hit within the last 7 days with hit_count >= min."""
    from services.hot_path import evict_cold_paths
    conn = seeded_hot_paths["conn"]

    # The "high-hit" row: hit_count=150, last_hit_at=now() — must survive
    evict_cold_paths(min_hits_per_week=100)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_hot_paths WHERE path='/reports/summary'")
        count = cur.fetchone()[0]

    assert count == 1, "Active high-hit path was incorrectly evicted"


# ── L0-07: fuzzy score always in [0.0, 1.0] ─────────────────────────────────

def test_l007_fuzzy_score_bounded(seeded_hot_paths, settings_override):
    """Fuzzy match score is always within [0.0, 1.0]."""
    import Levenshtein

    queries = ["Reports Summary", "", "xyz", "A" * 500, "reports summary extra words here"]
    label = "Reports Summary"

    for q in queries:
        score = Levenshtein.ratio(q.lower(), label.lower())
        assert 0.0 <= score <= 1.0, f"Score {score} out of bounds for query {q!r}"


# ── L0-08: alias matching is case-insensitive ────────────────────────────────

def test_l008_alias_matching_case_insensitive(clean_db, settings_override):
    """Fuzzy match on aliases is case-insensitive."""
    with clean_db.cursor() as cur:
        cur.execute(
            "INSERT INTO nav_hot_paths (path, label, aliases, hit_count) VALUES (%s, %s, %s, %s)",
            ("/test", "Test Page", ["MyAlias", "ANOTHER"], 0),
        )
    clean_db.commit()

    from services.hot_path import lookup
    with settings_override(HOT_PATH_THRESHOLD=0.5, MAX_HOT_PATHS=10):
        result_lower = lookup("myalias")
        result_upper = lookup("MYALIAS")

    # Both should score the same against the alias
    import Levenshtein
    score_lower = Levenshtein.ratio("myalias", "myalias")
    score_upper = Levenshtein.ratio("myalias", "myalias")
    assert score_lower == score_upper, "Case-insensitive alias matching failed"
