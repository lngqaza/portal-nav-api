"""
Miss-mining service — surfaces zero-result queries, clusters similar phrasings,
and suggests hot-path additions that would collapse the most misses.

Clustering uses Levenshtein ratio to group queries that say the same thing
in slightly different ways (e.g. "cant find my policy" / "find my policy").
Each cluster is ranked by frequency so the highest-impact additions surface first.
"""
import logging
from datetime import datetime, timedelta, timezone

import Levenshtein

from core.config import settings
from core.db import get_conn
from services.intent import intent_core

logger = logging.getLogger(__name__)


def get_miss_report(days: int = 7, site: str = None) -> dict:
    """
    Return a structured miss-mining report for the given window.

    Args:
        days: Number of days to look back.
        site: Site ID filter, or None for all sites.

    Returns:
        dict with keys: total_misses, unique_queries, clusters, window_days, site.
        clusters is a list of {representative, phrasings, count, suggested_label}
        sorted by frequency descending.
    """
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    # Parameterised: site_id is always bound as a query parameter, never interpolated.
    # The WHERE clause structure (two variants) is fixed SQL — no user input reaches
    # the string template.
    if site:
        params = [window_start, site]
        miss_sql = (
            "SELECT raw_query, COUNT(*) AS cnt FROM nav_query_log "
            "WHERE layer_used = 'MISS' AND created_at >= %s AND site_id = %s "
            "GROUP BY raw_query ORDER BY cnt DESC LIMIT 100"
        )
        count_sql = (
            "SELECT COUNT(*) FROM nav_query_log "
            "WHERE layer_used = 'MISS' AND created_at >= %s AND site_id = %s"
        )
    else:
        params = [window_start]
        miss_sql = (
            "SELECT raw_query, COUNT(*) AS cnt FROM nav_query_log "
            "WHERE layer_used = 'MISS' AND created_at >= %s "
            "GROUP BY raw_query ORDER BY cnt DESC LIMIT 100"
        )
        count_sql = (
            "SELECT COUNT(*) FROM nav_query_log "
            "WHERE layer_used = 'MISS' AND created_at >= %s"
        )

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(miss_sql, params)
                rows = cur.fetchall()
                cur.execute(count_sql, params)
                total_misses = cur.fetchone()[0]
    except Exception as exc:
        logger.warning("miss_report query failed: %s", exc)
        return {"total_misses": 0, "unique_queries": 0, "clusters": [], "window_days": days, "site": site or "all"}

    # Build (core, raw, count) list
    entries = []
    for raw, cnt in rows:
        core = intent_core(raw) or raw.lower().strip()
        entries.append((core, raw, cnt))

    # Greedy clustering by intent-core Levenshtein similarity
    clusters = []
    used = set()
    for i, (core_i, raw_i, cnt_i) in enumerate(entries):
        if i in used:
            continue
        members = [(raw_i, cnt_i)]
        used.add(i)
        total = cnt_i
        for j, (core_j, raw_j, cnt_j) in enumerate(entries):
            if j in used:
                continue
            if Levenshtein.ratio(core_i, core_j) >= settings.CLUSTER_SIMILARITY:
                members.append((raw_j, cnt_j))
                total += cnt_j
                used.add(j)
        if total < settings.MIN_CLUSTER_COUNT:
            continue
        # Pick the most frequent phrasing as the representative
        members.sort(key=lambda x: -x[1])
        representative = members[0][0]
        # Suggest a label: title-case the intent core
        suggested_label = core_i.title()
        clusters.append({
            "representative": representative,
            "phrasings": [m[0] for m in members[:10]],
            "count": total,
            "suggested_label": suggested_label,
        })

    clusters.sort(key=lambda c: -c["count"])

    return {
        "window_days": days,
        "site": site or "all",
        "total_misses": total_misses,
        "unique_queries": len(rows),
        "clusters": clusters[:50],
    }
