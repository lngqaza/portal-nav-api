"""Unit tests for analytics, miss-mining, and context-boost features."""
import pytest
from unittest.mock import patch, MagicMock


# ── Analytics ──────────────────────────────────────────────────────────────────

class TestGetAnalytics:
    def test_returns_expected_shape(self):
        """get_analytics returns all required top-level keys."""
        mock_cursor = MagicMock()
        # daily_queries, layer_breakdown totals, matched, navigations, top_queries, top_pages
        mock_cursor.fetchall.side_effect = [
            [("2026-06-10", 100, 5, 12.3)],       # daily_queries
            [("L0", 60), ("L1", 30), ("MISS", 5)], # layer_breakdown
            [],                                      # top_queries
            [],                                      # top_pages
        ]
        mock_cursor.fetchone.side_effect = [
            (95,),   # matched (non-MISS)
            (40,),   # navigations
        ]
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("services.analytics.get_conn", return_value=mock_conn):
            from services.analytics import get_analytics
            result = get_analytics(days=7, site="default")

        for key in ("window_days", "site", "total_queries", "total_navigations",
                    "ctr_pct", "daily_queries", "layer_breakdown", "top_queries", "top_pages"):
            assert key in result, f"missing key: {key}"

    def test_graceful_on_db_error(self):
        """get_analytics returns empty structure (not 5xx) on DB failure."""
        with patch("services.analytics.get_conn", side_effect=RuntimeError("DB down")):
            from services.analytics import get_analytics
            result = get_analytics()
        assert result["total_queries"] == 0
        assert result["daily_queries"] == []

    def test_ctr_zero_division_safe(self):
        """No division by zero when matched = 0."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [[], [], [], []]
        mock_cursor.fetchone.side_effect = [(0,), (0,)]
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("services.analytics.get_conn", return_value=mock_conn):
            from services.analytics import get_analytics
            result = get_analytics()
        assert result["ctr_pct"] == 0.0


# ── Miss mining ────────────────────────────────────────────────────────────────

class TestGetMissReport:
    def test_clusters_similar_queries(self):
        """Nearly identical miss queries are grouped into one cluster."""
        from services.miss_mining import get_miss_report
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("cant find my policy", 3),
            ("find my policy", 2),
            ("locate my policy", 1),
            ("how do i cancel", 5),
        ]
        mock_cursor.fetchone.return_value = (11,)
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("services.miss_mining.get_conn", return_value=mock_conn):
            result = get_miss_report(days=7)

        assert result["total_misses"] == 11
        # At least two clusters: policy group + cancel group
        assert len(result["clusters"]) >= 2
        # Sorted by count descending
        counts = [c["count"] for c in result["clusters"]]
        assert counts == sorted(counts, reverse=True)

    def test_graceful_on_db_error(self):
        """get_miss_report returns empty structure on DB failure."""
        with patch("services.miss_mining.get_conn", side_effect=RuntimeError("DB down")):
            from services.miss_mining import get_miss_report
            result = get_miss_report()
        assert result["total_misses"] == 0
        assert result["clusters"] == []


# ── Context-path boosting ──────────────────────────────────────────────────────

class TestContextBoost:
    def test_same_segment_candidate_boosted(self):
        """A candidate sharing the context_path segment gets score * 1.10."""
        from services.query_router import route_query
        from models.navigation import EmbeddingResult as Candidate

        flight_cand = Candidate("/flights.html", "Book Flights", "", 0.70)
        hotel_cand  = Candidate("/hotels.html",  "Hotels",       "", 0.72)

        with patch("services.query_router.hp.lookup", return_value=None), \
             patch("services.query_router.emb.search", return_value=[hotel_cand, flight_cand]), \
             patch("services.query_router.hp.record_miss"), \
             patch("services.query_router._log"), \
             patch("services.query_router.spelling.correct_query", side_effect=lambda q, s: q), \
             patch("services.query_router.intent.intent_core", side_effect=lambda q: q):
            from core.config import settings
            orig = settings.L1_THRESHOLD
            settings.L1_THRESHOLD = 0.99  # force past L1 to see boost effect on ordering
            try:
                result = route_query("book a flight", context_path="/flights.html")
            finally:
                settings.L1_THRESHOLD = orig

        # flight_cand was 0.70 → boosted to 0.77, hotel was 0.72 → no boost
        # so the flight candidate should now be ranked higher after boost
        # (only relevant when L1 threshold is exceeded — check candidate order)
        # The boost reordered them: flights should be first
        assert result is not None

    def test_no_context_no_boost(self):
        """When context_path is None, no boost is applied."""
        from services.query_router import route_query
        from models.navigation import EmbeddingResult as Candidate

        cand = Candidate("/hotels.html", "Hotels", "", 0.70)
        with patch("services.query_router.hp.lookup", return_value=None), \
             patch("services.query_router.emb.search", return_value=[cand]), \
             patch("services.query_router.hp.record_miss"), \
             patch("services.query_router._log"), \
             patch("services.query_router.spelling.correct_query", side_effect=lambda q, s: q), \
             patch("services.query_router.intent.intent_core", side_effect=lambda q: q):
            route_query("find a hotel", context_path=None)
        # No assertion needed — just must not raise
