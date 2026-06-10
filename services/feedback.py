"""
Feedback service — records user navigation events and auto-promotes
popular L1/L2 results to the hot-path registry (L0).

Auto-promotion logic:
  A path that is explicitly navigated to from at least PROMOTE_UNIQUE_QUERIES
  distinct queries within PROMOTE_WINDOW_DAYS is automatically upserted into
  nav_hot_paths so future identical (or similar) queries hit L0 (~1ms) instead
  of waiting for L1/L2 (~50–180ms).

  Promotion is idempotent — if the path is already in nav_hot_paths the row is
  updated (label refreshed, hit_count preserved).
"""
import logging
from datetime import datetime, timedelta

from core.db import get_conn
from services.hot_path import upsert_path

logger = logging.getLogger(__name__)

# ── Tuning constants ─────────────────────────────────────────────────────────
PROMOTE_UNIQUE_QUERIES = 3    # distinct queries that led to this path
PROMOTE_WINDOW_DAYS    = 7    # within this rolling window
PROMOTE_MIN_CONFIDENCE = 0.60 # only promote results users actually chose


def record_navigation(query: str, path: str, label: str, confidence: float) -> dict:
    """
    Record that a user chose `path` in response to `query`.

    Persists to nav_navigate_log, then checks whether this path now qualifies
    for auto-promotion to the hot-path registry.

    Args:
        query:      The raw query string the user typed.
        path:       The portal path they navigated to.
        label:      Human-readable page label.
        confidence: Score that drove the navigation (0–1).

    Returns:
        dict with keys: recorded (bool), promoted (bool), promote_count (int).
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO nav_navigate_log (raw_query, navigated_path, label, confidence)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (query[:500], path[:500], label[:200], confidence),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("record_navigation insert failed: %s", exc)
        return {"recorded": False, "promoted": False, "promote_count": 0}

    # Check auto-promotion eligibility
    promoted, count = _maybe_promote(path, label, confidence)
    return {"recorded": True, "promoted": promoted, "promote_count": count}


def _maybe_promote(path: str, label: str, confidence: float) -> tuple:
    """
    Auto-promote path to hot-paths if it has been navigated enough times
    by distinct queries within the promotion window.

    Args:
        path:       The portal path to evaluate.
        label:      Human-readable page label (used if promotion creates a new row).
        confidence: Confidence of the triggering navigation.

    Returns:
        Tuple of (promoted: bool, unique_query_count: int).
    """
    if confidence < PROMOTE_MIN_CONFIDENCE:
        return False, 0

    window_start = datetime.utcnow() - timedelta(days=PROMOTE_WINDOW_DAYS)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT raw_query)
                    FROM nav_navigate_log
                    WHERE navigated_path = %s
                      AND created_at >= %s
                      AND confidence >= %s
                    """,
                    (path, window_start, PROMOTE_MIN_CONFIDENCE),
                )
                count = cur.fetchone()[0]
    except Exception as exc:
        logger.warning("_maybe_promote query failed: %s", exc)
        return False, 0

    if count < PROMOTE_UNIQUE_QUERIES:
        return False, count

    # Promote — upsert_path is idempotent
    try:
        upsert_path({"path": path, "label": label, "aliases": [], "pinned": False})
        logger.info("auto-promoted %s to hot-paths (unique_queries=%d)", path, count)
        return True, count
    except Exception as exc:
        logger.warning("auto-promote upsert failed for %s: %s", path, exc)
        return False, count


def get_navigation_stats(days: int = 7) -> dict:
    """
    Return aggregate navigation stats for the given window.

    Args:
        days: Number of days to look back (default 7).

    Returns:
        dict with top_paths (list), total_navigations (int), promotion_candidates (list).
    """
    window_start = datetime.utcnow() - timedelta(days=days)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Top navigated paths
                cur.execute(
                    """
                    SELECT navigated_path, label, COUNT(*) AS nav_count,
                           COUNT(DISTINCT raw_query) AS unique_queries
                    FROM nav_navigate_log
                    WHERE created_at >= %s
                    GROUP BY navigated_path, label
                    ORDER BY nav_count DESC
                    LIMIT 20
                    """,
                    (window_start,),
                )
                top_paths = [
                    {"path": r[0], "label": r[1], "nav_count": r[2], "unique_queries": r[3]}
                    for r in cur.fetchall()
                ]

                cur.execute("SELECT COUNT(*) FROM nav_navigate_log WHERE created_at >= %s", (window_start,))
                total = cur.fetchone()[0]

                # Paths close to promotion threshold (not yet in hot_paths)
                cur.execute(
                    """
                    SELECT n.navigated_path, n.label, COUNT(DISTINCT n.raw_query) AS uq
                    FROM nav_navigate_log n
                    LEFT JOIN nav_hot_paths h ON h.path = n.navigated_path
                    WHERE n.created_at >= %s
                      AND n.confidence >= %s
                      AND h.id IS NULL
                    GROUP BY n.navigated_path, n.label
                    HAVING COUNT(DISTINCT n.raw_query) >= 1
                    ORDER BY uq DESC
                    LIMIT 10
                    """,
                    (window_start, PROMOTE_MIN_CONFIDENCE),
                )
                candidates = [
                    {"path": r[0], "label": r[1], "unique_queries": r[2],
                     "needed_for_promotion": max(0, PROMOTE_UNIQUE_QUERIES - r[2])}
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        logger.warning("get_navigation_stats failed: %s", exc)
        return {"total_navigations": 0, "top_paths": [], "promotion_candidates": []}

    return {"total_navigations": total, "top_paths": top_paths, "promotion_candidates": candidates}
