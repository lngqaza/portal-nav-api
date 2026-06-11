"""
FEEDBACK invariants — record_navigation, _learn_alias, _maybe_promote.

All tests require a live DB connection; they skip with integration-pending[rds]
when the RDS host is unreachable (same pattern as the rest of the invariant suite).
"""
import pytest
from unittest.mock import patch


# ── FB-01: record_navigation writes to nav_navigate_log ──────────────────────

def test_fb01_record_navigation_inserts_row(clean_db):
    """record_navigation persists a row and returns recorded=True."""
    from services.feedback import record_navigation

    result = record_navigation(
        query="submit a claim",
        path="/claims/submit",
        label="Submit Claim",
        confidence=0.85,
        site="default",
    )

    assert result["recorded"] is True

    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT raw_query, navigated_path, site_id FROM nav_navigate_log "
            "WHERE navigated_path = '/claims/submit'"
        )
        row = cur.fetchone()

    assert row is not None, "Expected a row in nav_navigate_log"
    assert row[0] == "submit a claim"
    assert row[2] == "default"


def test_fb01_record_navigation_truncates_to_500(clean_db):
    """Long query and path are truncated to their column limits."""
    from services.feedback import record_navigation

    long_query = "x" * 600
    long_path  = "/" + "p" * 600

    result = record_navigation(
        query=long_query,
        path=long_path,
        label="Test",
        confidence=0.7,
        site="default",
    )

    assert result["recorded"] is True

    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT length(raw_query), length(navigated_path) FROM nav_navigate_log "
            "WHERE label = 'Test'"
        )
        row = cur.fetchone()

    assert row[0] <= 500, f"raw_query not truncated: {row[0]}"
    assert row[1] <= 500, f"navigated_path not truncated: {row[1]}"


# ── FB-02: _learn_alias attaches query core to hot_path row ──────────────────

def test_fb02_learn_alias_creates_entry(clean_db):
    """_learn_alias inserts a new hot_path row when the path isn't known yet."""
    from services.feedback import _learn_alias

    learned = _learn_alias(
        path="/claims/submit",
        label="Submit Claim",
        query="log my claim",
        site="default",
    )

    assert learned is True

    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT aliases FROM nav_hot_paths WHERE path = '/claims/submit' AND site_id = 'default'"
        )
        row = cur.fetchone()

    assert row is not None
    assert len(row[0]) > 0, "Expected at least one alias"


def test_fb02_learn_alias_deduplicates(clean_db):
    """_learn_alias does not add a near-duplicate alias (Levenshtein >= DUP_RATIO)."""
    from services.feedback import _learn_alias

    # Seed a hot_path row with an alias
    with clean_db.cursor() as cur:
        cur.execute(
            "INSERT INTO nav_hot_paths (site_id, path, label, aliases, pinned) "
            "VALUES ('default', '/claims/submit', 'Submit Claim', ARRAY['submit claim'], false)"
        )
    clean_db.commit()

    # "submit claims" is ~95% similar to "submit claim"
    learned = _learn_alias("/claims/submit", "Submit Claim", "submit claims", "default")

    assert learned is False, "Near-duplicate alias should not be added"


def test_fb02_learn_alias_ignores_essay_length_queries(clean_db):
    """Queries longer than ALIAS_MAX_LEN are silently ignored."""
    from services.feedback import _learn_alias

    long_query = "please help me find the claims submission form because I need to " * 5  # > 60 chars

    learned = _learn_alias("/claims/submit", "Submit Claim", long_query, "default")

    assert learned is False


# ── FB-03: _maybe_promote does not promote below confidence threshold ─────────

def test_fb03_no_promote_below_confidence(clean_db):
    """Paths with confidence < PROMOTE_MIN_CONFIDENCE are never promoted."""
    from services.feedback import _maybe_promote
    from core.config import settings

    promoted, count = _maybe_promote(
        path="/claims/submit",
        label="Submit Claim",
        confidence=settings.PROMOTE_MIN_CONFIDENCE - 0.01,
        site="default",
    )

    assert promoted is False
    assert count == 0


def test_fb03_no_promote_below_unique_query_threshold(clean_db):
    """Path with fewer than PROMOTE_UNIQUE_QUERIES unique queries is not promoted."""
    from services.feedback import _maybe_promote
    from core.config import settings

    # Insert fewer unique queries than required threshold
    with clean_db.cursor() as cur:
        for i in range(settings.PROMOTE_UNIQUE_QUERIES - 1):
            cur.execute(
                "INSERT INTO nav_navigate_log (raw_query, navigated_path, label, confidence, site_id) "
                "VALUES (%s, '/test-path', 'Test', %s, 'default')",
                (f"unique query {i}", settings.PROMOTE_MIN_CONFIDENCE),
            )
    clean_db.commit()

    promoted, count = _maybe_promote(
        path="/test-path",
        label="Test",
        confidence=settings.PROMOTE_MIN_CONFIDENCE,
        site="default",
    )

    assert promoted is False
    assert count == settings.PROMOTE_UNIQUE_QUERIES - 1


def test_fb03_promotes_when_threshold_met(clean_db):
    """Path reaching PROMOTE_UNIQUE_QUERIES distinct queries within window is promoted."""
    from services.feedback import _maybe_promote
    from core.config import settings

    with clean_db.cursor() as cur:
        for i in range(settings.PROMOTE_UNIQUE_QUERIES):
            cur.execute(
                "INSERT INTO nav_navigate_log (raw_query, navigated_path, label, confidence, site_id) "
                "VALUES (%s, '/promote-me', 'Promote Me', %s, 'default')",
                (f"distinct query {i}", settings.PROMOTE_MIN_CONFIDENCE),
            )
    clean_db.commit()

    promoted, count = _maybe_promote(
        path="/promote-me",
        label="Promote Me",
        confidence=settings.PROMOTE_MIN_CONFIDENCE,
        site="default",
    )

    assert promoted is True
    assert count >= settings.PROMOTE_UNIQUE_QUERIES

    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM nav_hot_paths WHERE path = '/promote-me' AND site_id = 'default'"
        )
        hp_count = cur.fetchone()[0]

    assert hp_count == 1, "Path should be in nav_hot_paths after promotion"


# ── FB-04: promotion is idempotent ────────────────────────────────────────────

def test_fb04_double_promote_does_not_duplicate(clean_db):
    """Promoting a path that is already in nav_hot_paths does not create a second row."""
    from services.feedback import _maybe_promote
    from core.config import settings

    with clean_db.cursor() as cur:
        for i in range(settings.PROMOTE_UNIQUE_QUERIES):
            cur.execute(
                "INSERT INTO nav_navigate_log (raw_query, navigated_path, label, confidence, site_id) "
                "VALUES (%s, '/idempotent-path', 'Idempotent', %s, 'default')",
                (f"query {i}", settings.PROMOTE_MIN_CONFIDENCE),
            )
    clean_db.commit()

    _maybe_promote("/idempotent-path", "Idempotent", settings.PROMOTE_MIN_CONFIDENCE, "default")
    _maybe_promote("/idempotent-path", "Idempotent Updated", settings.PROMOTE_MIN_CONFIDENCE, "default")

    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*), MAX(label) FROM nav_hot_paths "
            "WHERE path = '/idempotent-path' AND site_id = 'default'"
        )
        count, label = cur.fetchone()

    assert count == 1, "Idempotent promotion should not create duplicate rows"
    assert label == "Idempotent Updated", "Second call should refresh label"
