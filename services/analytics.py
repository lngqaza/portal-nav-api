"""
Analytics service — click-through rates, daily query volume, layer breakdown,
top queries and pages.  All reads; no writes.
"""
import logging
from datetime import datetime, timedelta

from core.db import get_conn

logger = logging.getLogger(__name__)

# Sentinel used in parameterised WHERE branches below.
_NO_SITE = object()


def _qlog_params(window_start, site):
    """Return (site_clause, params) for nav_query_log queries."""
    if site:
        return "AND site_id = %s", [window_start, site]
    return "", [window_start]


def _nlog_params(window_start, site):
    """Return (site_clause, params) for nav_navigate_log queries."""
    if site:
        return "AND site_id = %s", [window_start, site]
    return "", [window_start]


def get_analytics(days: int = 7, site: str = None) -> dict:
    """
    Return full analytics for the given window, optionally filtered to a site.

    Args:
        days: Number of days to look back (default 7).
        site: Site ID to filter by, or None for all sites.

    Returns:
        dict with keys: daily_queries, layer_breakdown, ctr_pct, top_queries, top_pages.
    """
    window_start = datetime.utcnow() - timedelta(days=days)
    q_clause, q_params = _qlog_params(window_start, site)
    n_clause, n_params = _nlog_params(window_start, site)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Daily query volume + miss rate + avg response time
                cur.execute(
                    """
                    SELECT
                        date_trunc('day', created_at)::date AS day,
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE layer_used = 'MISS') AS misses,
                        ROUND(AVG(response_ms)::numeric, 1) AS avg_ms
                    FROM nav_query_log
                    WHERE created_at >= %s
                    """ + (f" {q_clause}" if q_clause else "") + """
                    GROUP BY 1
                    ORDER BY 1
                    """,
                    q_params,
                )
                daily_queries = [
                    {
                        "date": str(r[0]),
                        "total": r[1],
                        "miss_rate": round(r[2] / max(r[1], 1) * 100, 1),
                        "avg_ms": float(r[3] or 0),
                    }
                    for r in cur.fetchall()
                ]

                # Layer breakdown over the whole window
                cur.execute(
                    """
                    SELECT layer_used, COUNT(*) AS cnt
                    FROM nav_query_log
                    WHERE created_at >= %s
                    """ + (f" {q_clause}" if q_clause else "") + """
                    GROUP BY layer_used
                    ORDER BY cnt DESC
                    """,
                    q_params,
                )
                layer_rows = cur.fetchall()
                total_queries = sum(r[1] for r in layer_rows)
                layer_breakdown = {
                    r[0]: {
                        "count": r[1],
                        "pct": round(r[1] / max(total_queries, 1) * 100, 1),
                    }
                    for r in layer_rows
                }

                # Click-through rate: navigations / non-MISS queries
                cur.execute(
                    """
                    SELECT COUNT(*) FROM nav_query_log
                    WHERE created_at >= %s AND layer_used != 'MISS'
                    """ + (f" {q_clause}" if q_clause else ""),
                    q_params,
                )
                matched = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM nav_navigate_log
                    WHERE created_at >= %s
                    """ + (f" {n_clause}" if n_clause else ""),
                    n_params,
                )
                navigations = cur.fetchone()[0]
                ctr = round(navigations / max(matched, 1) * 100, 1)

                # Top 20 queries (excluding MISS, most frequent)
                cur.execute(
                    """
                    SELECT raw_query, COUNT(*) AS cnt,
                           MAX(layer_used) AS layer,
                           ROUND(AVG(confidence)::numeric, 3) AS avg_conf
                    FROM nav_query_log
                    WHERE created_at >= %s AND layer_used != 'MISS'
                    """ + (f" {q_clause}" if q_clause else "") + """
                    GROUP BY raw_query
                    ORDER BY cnt DESC
                    LIMIT 20
                    """,
                    q_params,
                )
                top_queries = [
                    {"query": r[0], "count": r[1], "layer": r[2], "avg_confidence": float(r[3] or 0)}
                    for r in cur.fetchall()
                ]

                # Top pages by navigation count with avg confidence
                cur.execute(
                    """
                    SELECT navigated_path, label, COUNT(*) AS nav_count,
                           ROUND(AVG(confidence)::numeric, 3) AS avg_conf,
                           COUNT(DISTINCT raw_query) AS unique_queries
                    FROM nav_navigate_log
                    WHERE created_at >= %s
                    """ + (f" {n_clause}" if n_clause else "") + """
                    GROUP BY navigated_path, label
                    ORDER BY nav_count DESC
                    LIMIT 20
                    """,
                    n_params,
                )
                top_pages = [
                    {
                        "path": r[0],
                        "label": r[1],
                        "navigations": r[2],
                        "avg_confidence": float(r[3] or 0),
                        "unique_queries": r[4],
                    }
                    for r in cur.fetchall()
                ]

    except Exception as exc:
        logger.warning("get_analytics failed: %s", exc)
        return {
            "total_queries": 0,
            "total_navigations": 0,
            "ctr_pct": 0,
            "daily_queries": [],
            "layer_breakdown": {},
            "top_queries": [],
            "top_pages": [],
        }

    return {
        "window_days": days,
        "site": site or "all",
        "total_queries": total_queries,
        "total_navigations": navigations,
        "ctr_pct": ctr,
        "daily_queries": daily_queries,
        "layer_breakdown": layer_breakdown,
        "top_queries": top_queries,
        "top_pages": top_pages,
    }
