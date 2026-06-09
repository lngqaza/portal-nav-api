"""L0: Hot path registry — fuzzy string match against top-N usage-ranked paths."""
import logging
from typing import Optional

import Levenshtein

from core.config import settings
from core.db import get_conn
from models.navigation import HotPathResult

logger = logging.getLogger(__name__)


def lookup(query: str) -> Optional[HotPathResult]:
    q = query.lower().strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, path, label, aliases, hit_count, last_hit_at, pinned
                FROM nav_hot_paths
                ORDER BY (
                    hit_count
                    * CASE WHEN last_hit_at > now() - interval '30 days' THEN 1.0 ELSE 0.5 END
                    + CASE WHEN pinned THEN 10000 ELSE 0 END
                ) DESC
                LIMIT %s
                """,
                (settings.MAX_HOT_PATHS,),
            )
            rows = cur.fetchall()

    if not rows:
        return None

    best_score, best_row = 0.0, None
    total = len(rows)

    for idx, row in enumerate(rows):
        lev_label = Levenshtein.ratio(q, (row[2] or "").lower())
        aliases = row[3] or []
        lev_alias = max((Levenshtein.ratio(q, a.lower()) for a in aliases), default=0.0)
        rank_pct = 1.0 - (idx / max(total, 1))
        score = 0.4 * lev_label + 0.4 * lev_alias + 0.2 * rank_pct

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


def record_miss(query: str):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO nav_query_log (raw_query,layer_used,confidence,response_ms) VALUES (%s,'MISS',0.0,0)",
                    (query[:500],),
                )
            conn.commit()
    except Exception as e:
        logger.warning("record_miss failed: %s", e)


def get_top_paths(limit: int = 70) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
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


def upsert_path(data: dict) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nav_hot_paths WHERE path=%s", (data["path"],))
            if cur.fetchone():
                cur.execute(
                    "UPDATE nav_hot_paths SET label=%s,aliases=%s,pinned=%s,updated_at=now() WHERE path=%s",
                    (data["label"], data.get("aliases", []), data.get("pinned", False), data["path"]),
                )
            else:
                cur.execute(
                    "INSERT INTO nav_hot_paths (path,label,aliases,pinned) VALUES (%s,%s,%s,%s)",
                    (data["path"], data["label"], data.get("aliases", []), data.get("pinned", False)),
                )
            cur.execute("SELECT id,path,label FROM nav_hot_paths WHERE path=%s", (data["path"],))
            row = cur.fetchone()
        conn.commit()
    return {"id": str(row[0]), "path": row[1], "label": row[2]}


def evict_cold_paths(min_hits_per_week: int = 50) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM nav_hot_paths
                WHERE pinned=false
                AND (last_hit_at IS NULL OR last_hit_at < now() - interval '7 days')
                AND hit_count < %s
                """,
                (min_hits_per_week,),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted
