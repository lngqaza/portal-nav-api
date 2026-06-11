"""L0: Hot path registry — fuzzy string match against top-N usage-ranked paths."""
import logging
import re
from typing import Optional

import Levenshtein

from core.config import settings
from core.db import get_conn
from models.navigation import HotPathResult
from services.intent import STOPWORDS

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Stopword-free form so "log my claims" still matches alias "log claims"."""
    return " ".join(w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOPWORDS)


def _sim(q: str, qn: str, target: str) -> float:
    """Best similarity between the query (raw + normalised) and a target string."""
    t = (target or "").lower()
    return max(Levenshtein.ratio(q, t), Levenshtein.ratio(qn, _norm(t)))


def lookup(query: str, scope: list = None) -> Optional[HotPathResult]:
    scope = scope or ["default"]
    q = query.lower().strip()
    qn = _norm(q) or q
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, path, label, aliases, hit_count, last_hit_at, pinned, site_id
                    FROM nav_hot_paths
                    WHERE site_id = ANY(%s)
                    ORDER BY (
                        hit_count
                        * CASE WHEN last_hit_at > now() - interval '30 days' THEN 1.0 ELSE 0.5 END
                        + CASE WHEN pinned THEN 10000 ELSE 0 END
                    ) DESC
                    LIMIT %s
                    """,
                    (scope, settings.MAX_HOT_PATHS),
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.warning("hot_path lookup failed: %s", exc)
        return None

    if not rows:
        return None

    best_score, best_row = 0.0, None
    total = len(rows)

    for idx, row in enumerate(rows):
        lev_label = _sim(q, qn, row[2])
        aliases = row[3] or []
        lev_alias = max((_sim(q, qn, a) for a in aliases), default=0.0)
        rank_pct = 1.0 - (idx / max(total, 1))
        # Best text match dominates: a learned alias that matches the query
        # exactly must clear HOT_PATH_THRESHOLD on its own — the old
        # 0.4/0.4/0.2 split capped a perfect alias at ~0.65 when the label
        # differed, silently disabling phrase learning.
        score = 0.8 * max(lev_label, lev_alias) + 0.2 * rank_pct
        if row[7] != scope[0]:
            score *= settings.CROSS_SITE_PENALTY  # home-site results win ties

        if score > best_score:
            best_score, best_row = score, row

    if best_score >= settings.HOT_PATH_THRESHOLD and best_row:
        _increment_hit(str(best_row[0]))
        return HotPathResult(
            path=best_row[1], label=best_row[2],
            confidence=round(best_score, 4), hit_count=best_row[4],
        )
    return None


def _increment_hit(path_id: str):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE nav_hot_paths SET hit_count = hit_count+1, last_hit_at=now() WHERE id=%s",
                    (path_id,),
                )
            conn.commit()
    except Exception as e:
        logger.warning("hit increment failed: %s", e)


def get_top_paths(limit: int = 70, site: str = None) -> list:
    """
    Return hot-path rows ordered by popularity.

    Args:
        limit: Maximum rows to return.
        site:  When provided, restrict to this tenant only. None returns all
               tenants (admin overview only — never use without site in
               production query serving).
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if site:
                    cur.execute(
                        """
                        SELECT id, path, label, aliases, hit_count, last_hit_at, pinned, created_at
                        FROM nav_hot_paths
                        WHERE site_id = %s
                        ORDER BY (hit_count + CASE WHEN pinned THEN 10000 ELSE 0 END) DESC
                        LIMIT %s
                        """,
                        (site, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, path, label, aliases, hit_count, last_hit_at, pinned, created_at
                        FROM nav_hot_paths
                        ORDER BY (hit_count + CASE WHEN pinned THEN 10000 ELSE 0 END) DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as exc:
        logger.warning("get_top_paths failed: %s", exc)
        return []


def upsert_path(data: dict) -> dict:
    """
    Insert or update a hot-path entry atomically.

    Uses INSERT ... ON CONFLICT (path) DO UPDATE so the operation is a single
    atomic statement — no SELECT-then-INSERT race condition that the old
    implementation had.  The uq_hot_paths_path UNIQUE constraint (added in
    migration 001) is the conflict target.

    Args:
        data: dict with keys path (str), label (str), aliases (list), pinned (bool).

    Returns:
        dict with id, path, label of the upserted row.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO nav_hot_paths (site_id, path, label, aliases, pinned)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (site_id, path) DO UPDATE
                        SET label      = EXCLUDED.label,
                            aliases    = EXCLUDED.aliases,
                            pinned     = EXCLUDED.pinned,
                            updated_at = now()
                    RETURNING id, path, label
                    """,
                    (
                        data.get("site", "default"),
                        data["path"],
                        data["label"],
                        data.get("aliases", []),
                        data.get("pinned", False),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return {"id": str(row[0]), "path": row[1], "label": row[2]}
    except Exception as exc:
        logger.warning("upsert_path failed: %s", exc)
        raise


def evict_cold_paths(min_hits_per_week: int = 50, site: str = None) -> int:
    """
    Delete unpinned paths that haven't been hit recently enough.

    Args:
        min_hits_per_week: Paths with fewer total hits are candidates for eviction.
        site: When provided, restrict eviction to this tenant. Never evict
              cross-tenant — callers must pass the authenticated site_id.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if site:
                    cur.execute(
                        """
                        DELETE FROM nav_hot_paths
                        WHERE site_id = %s
                          AND pinned = false
                          AND (last_hit_at IS NULL OR last_hit_at < now() - interval '7 days')
                          AND hit_count < %s
                        """,
                        (site, min_hits_per_week),
                    )
                else:
                    cur.execute(
                        """
                        DELETE FROM nav_hot_paths
                        WHERE pinned = false
                          AND (last_hit_at IS NULL OR last_hit_at < now() - interval '7 days')
                          AND hit_count < %s
                        """,
                        (min_hits_per_week,),
                    )
                deleted = cur.rowcount
            conn.commit()
        return deleted
    except Exception as exc:
        logger.warning("evict_cold_paths failed: %s", exc)
        return 0
