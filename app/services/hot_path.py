import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List

import Levenshtein
from sqlalchemy import text, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.navigation import NavHotPath, NavQueryLog


@dataclass
class HotPathResult:
    path: str
    label: str
    confidence: float
    hit_count: int


async def lookup(query: str, session: AsyncSession, max_paths: int = None) -> Optional[HotPathResult]:
    max_paths = max_paths or settings.MAX_HOT_PATHS
    result = await session.execute(
        text("""
            SELECT id, path, label, aliases, hit_count, last_hit_at, pinned
            FROM nav_hot_paths
            ORDER BY (hit_count + CASE WHEN pinned THEN 10000 ELSE 0 END) DESC
            LIMIT :limit
        """),
        {"limit": max_paths}
    )
    rows = result.fetchall()
    if not rows:
        return None

    q = query.lower().strip()
    best_score = 0.0
    best_row = None
    best_rank_pct = 0.0

    for idx, row in enumerate(rows):
        recency_weight = 1.0
        if row.last_hit_at:
            age_days = (datetime.utcnow() - row.last_hit_at).days
            if age_days > 30:
                recency_weight = 0.5

        rank_score = (row.hit_count * recency_weight) + (10000 if row.pinned else 0)
        rank_pct = 1.0 - (idx / max(len(rows), 1))

        lev_label = Levenshtein.ratio(q, row.label.lower())
        aliases = row.aliases or []
        lev_alias = max([Levenshtein.ratio(q, a.lower()) for a in aliases], default=0.0) if aliases else 0.0

        score = 0.4 * lev_label + 0.4 * lev_alias + 0.2 * rank_pct

        if score > best_score:
            best_score = score
            best_row = row
            best_rank_pct = rank_pct

    if best_score >= settings.HOT_PATH_THRESHOLD and best_row:
        asyncio.create_task(_increment_hit(session, str(best_row.id)))
        return HotPathResult(
            path=best_row.path,
            label=best_row.label,
            confidence=round(best_score, 4),
            hit_count=best_row.hit_count,
        )
    return None


async def _increment_hit(session: AsyncSession, path_id: str):
    try:
        await session.execute(
            text("UPDATE nav_hot_paths SET hit_count = hit_count + 1, last_hit_at = now() WHERE id = :id"),
            {"id": path_id}
        )
        await session.commit()
    except Exception as e:
        logging.error("Failed to increment hit count: %s", e)


async def record_miss(session: AsyncSession, query: str):
    try:
        await session.execute(
            text("INSERT INTO nav_query_log (id, raw_query, layer_used, confidence, response_ms, created_at) VALUES (gen_random_uuid(), :q, 'MISS', 0.0, 0, now())"),
            {"q": query[:500]}
        )
        await session.commit()
    except Exception as e:
        logging.error("Failed to record miss: %s", e)


async def get_top_paths(session: AsyncSession, limit: int = 70) -> List[NavHotPath]:
    result = await session.execute(
        text("SELECT * FROM nav_hot_paths ORDER BY (hit_count + CASE WHEN pinned THEN 10000 ELSE 0 END) DESC LIMIT :limit"),
        {"limit": limit}
    )
    return result.fetchall()


async def upsert_path(session: AsyncSession, data: dict) -> NavHotPath:
    existing = await session.execute(
        text("SELECT id FROM nav_hot_paths WHERE path = :path"),
        {"path": data["path"]}
    )
    row = existing.fetchone()
    if row:
        await session.execute(
            text("UPDATE nav_hot_paths SET label=:label, aliases=:aliases, pinned=:pinned, updated_at=now() WHERE path=:path"),
            {"label": data["label"], "aliases": data.get("aliases", []), "pinned": data.get("pinned", False), "path": data["path"]}
        )
    else:
        await session.execute(
            text("INSERT INTO nav_hot_paths (id, path, label, aliases, hit_count, pinned, created_at, updated_at) VALUES (gen_random_uuid(), :path, :label, :aliases, 0, :pinned, now(), now())"),
            {"path": data["path"], "label": data["label"], "aliases": data.get("aliases", []), "pinned": data.get("pinned", False)}
        )
    await session.commit()
    result = await session.execute(text("SELECT * FROM nav_hot_paths WHERE path = :path"), {"path": data["path"]})
    return result.fetchone()


async def evict_cold_paths(session: AsyncSession, min_hits_per_week: int = 50):
    cutoff = datetime.utcnow() - timedelta(days=7)
    await session.execute(
        text("DELETE FROM nav_hot_paths WHERE pinned = false AND (last_hit_at IS NULL OR last_hit_at < :cutoff) AND hit_count < :min_hits"),
        {"cutoff": cutoff, "min_hits": min_hits_per_week}
    )
    await session.commit()
    logging.info("Evicted cold hot paths with fewer than %d hits/week", min_hits_per_week)
