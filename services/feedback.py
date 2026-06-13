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
from datetime import datetime, timedelta, timezone

import Levenshtein

from core.config import settings
from core.db import get_conn
from services.intent import intent_core

logger = logging.getLogger(__name__)


def record_navigation(query: str, path: str, label: str, confidence: float, site: str = "default") -> dict:
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
                    INSERT INTO nav_navigate_log (raw_query, navigated_path, label, confidence, site_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (query[:500], path[:500], label[:200], confidence, site),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("record_navigation insert failed: %s", exc)
        return {"recorded": False, "promoted": False, "promote_count": 0}

    # Learn this phrasing: the user just confirmed that `query` means `path`,
    # so its intent core becomes a hot-path alias. Next time the same (or a
    # similar) question is asked it resolves at L0 with high confidence —
    # the engine literally gets smarter with every navigation.
    learned = _learn_alias(path, label, query, site)

    # Check auto-promotion eligibility
    promoted, count = _maybe_promote(path, label, confidence, site)
    return {"recorded": True, "promoted": promoted, "promote_count": count, "alias_learned": learned}


def _learn_alias(path: str, label: str, query: str, site: str = "default") -> bool:
    """Attach the query's intent core as an alias on the path's hot-path row.

    Creates the row if the path isn't hot yet. Aliases are deduped with a
    Levenshtein similarity check (>= ALIAS_DUP_RATIO counts as already known)
    and capped at MAX_ALIASES, evicting the oldest learned phrasing first.

    Returns True if a new alias was stored.
    """
    core = intent_core(query)
    if not core or len(core) > settings.ALIAS_MAX_LEN:
        return False
    if core == (label or "").lower().strip():
        return False  # the label itself already matches at L0
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, aliases FROM nav_hot_paths WHERE site_id = %s AND path = %s", (site, path))
                row = cur.fetchone()
                if row:
                    aliases = row[1] or []
                    if any(Levenshtein.ratio(core, a.lower()) >= settings.ALIAS_DUP_RATIO for a in aliases):
                        return False
                    aliases = (aliases + [core])[-settings.MAX_ALIASES:]
                    cur.execute(
                        "UPDATE nav_hot_paths SET aliases = %s, updated_at = now() WHERE id = %s",
                        (aliases, row[0]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO nav_hot_paths (site_id, path, label, aliases, pinned)
                        VALUES (%s, %s, %s, %s, false)
                        ON CONFLICT (site_id, path) DO NOTHING
                        """,
                        (site, path, label, [core]),
                    )
            conn.commit()
        logger.info("learned alias %r for %s", core, path)
        return True
    except Exception as exc:
        logger.warning("_learn_alias failed for %s: %s", path, exc)
        return False


def _maybe_promote(path: str, label: str, confidence: float, site: str = "default") -> tuple:
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
    if confidence < settings.PROMOTE_MIN_CONFIDENCE:
        return False, 0

    window_start = datetime.now(timezone.utc) - timedelta(days=settings.PROMOTE_WINDOW_DAYS)
    # Single connection: count + conditional upsert in one transaction to
    # eliminate the two-connection race that could double-promote.
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT raw_query)
                    FROM nav_navigate_log
                    WHERE navigated_path = %s
                      AND site_id = %s
                      AND created_at >= %s
                      AND confidence >= %s
                    """,
                    (path, site, window_start, settings.PROMOTE_MIN_CONFIDENCE),
                )
                count = cur.fetchone()[0]
                if count < settings.PROMOTE_UNIQUE_QUERIES:
                    return False, count
                # Promote — insert if absent, refresh only the label if present.
                # Must NOT overwrite aliases: _learn_alias accumulates learned
                # phrasings and a blanket upsert would wipe them.
                cur.execute(
                    """
                    INSERT INTO nav_hot_paths (site_id, path, label, aliases, pinned)
                    VALUES (%s, %s, %s, '{}', false)
                    ON CONFLICT (site_id, path) DO UPDATE
                        SET label      = EXCLUDED.label,
                            updated_at = now()
                    """,
                    # aliases intentionally excluded from DO UPDATE — _learn_alias
                    # accumulates learned phrasings and a blanket overwrite would wipe them.
                    (site, path, label),
                )
            conn.commit()
        logger.info("auto-promoted %s to hot-paths (unique_queries=%d)", path, count)
        return True, count
    except Exception as exc:
        logger.warning("_maybe_promote failed for %s: %s", path, exc)
        return False, 0


def get_navigation_stats(days: int = 7, site: str = None) -> dict:
    """
    Return aggregate navigation stats for the given window.

    Args:
        days: Number of days to look back (default 7).
        site: Site ID to filter by, or None for all sites (admin only).

    Returns:
        dict with top_paths (list), total_navigations (int), promotion_candidates (list).
    """
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    # Build parameterised clauses — site value only ever travels through %s,
    # never interpolated into the SQL string.
    conditions = ["created_at >= %s"]
    base_params: list = [window_start]
    if site:
        conditions.append("site_id = %s")
        base_params.append(site)
    where = " AND ".join(conditions)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Top navigated paths
                cur.execute(
                    f"""
                    SELECT navigated_path, label, COUNT(*) AS nav_count,
                           COUNT(DISTINCT raw_query) AS unique_queries
                    FROM nav_navigate_log
                    WHERE {where}
                    GROUP BY navigated_path, label
                    ORDER BY nav_count DESC
                    LIMIT 20
                    """,
                    base_params,
                )
                top_paths = [
                    {"path": r[0], "label": r[1], "nav_count": r[2], "unique_queries": r[3]}
                    for r in cur.fetchall()
                ]

                cur.execute(
                    f"SELECT COUNT(*) FROM nav_navigate_log WHERE {where}",
                    base_params,
                )
                total = cur.fetchone()[0]

                # Paths close to promotion threshold (not yet in hot_paths for this site).
                # The JOIN is scoped to the same site_id so cross-tenant hot-paths don't
                # suppress promotion candidates for a different tenant.
                if site:
                    cur.execute(
                        """
                        SELECT n.navigated_path, n.label, COUNT(DISTINCT n.raw_query) AS uq
                        FROM nav_navigate_log n
                        LEFT JOIN nav_hot_paths h
                               ON h.path = n.navigated_path AND h.site_id = n.site_id
                        WHERE n.created_at >= %s
                          AND n.site_id = %s
                          AND n.confidence >= %s
                          AND h.id IS NULL
                        GROUP BY n.navigated_path, n.label
                        HAVING COUNT(DISTINCT n.raw_query) >= %s
                        ORDER BY uq DESC
                        LIMIT 10
                        """,
                        (window_start, site, settings.PROMOTE_MIN_CONFIDENCE,
                         settings.PROMOTE_UNIQUE_QUERIES),
                    )
                else:
                    cur.execute(
                        """
                        SELECT n.navigated_path, n.label, COUNT(DISTINCT n.raw_query) AS uq
                        FROM nav_navigate_log n
                        LEFT JOIN nav_hot_paths h
                               ON h.path = n.navigated_path AND h.site_id = n.site_id
                        WHERE n.created_at >= %s
                          AND n.confidence >= %s
                          AND h.id IS NULL
                        GROUP BY n.navigated_path, n.label
                        HAVING COUNT(DISTINCT n.raw_query) >= %s
                        ORDER BY uq DESC
                        LIMIT 10
                        """,
                        (window_start, settings.PROMOTE_MIN_CONFIDENCE,
                         settings.PROMOTE_UNIQUE_QUERIES),
                    )
                candidates = [
                    {"path": r[0], "label": r[1], "unique_queries": r[2],
                     "needed_for_promotion": max(0, settings.PROMOTE_UNIQUE_QUERIES - r[2])}
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        logger.warning("get_navigation_stats failed: %s", exc)
        return {"total_navigations": 0, "top_paths": [], "promotion_candidates": []}

    return {"total_navigations": total, "top_paths": top_paths, "promotion_candidates": candidates}
