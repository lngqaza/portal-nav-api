from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.database import get_session
from app.models.navigation import NavHotPath, NavIndex, NavQueryLog
import app.services.hot_path as hp
import app.services.embedding as emb

router = APIRouter(dependencies=[Depends(require_admin)])


class HotPathBody(BaseModel):
    path: str
    label: str
    aliases: list = []
    pinned: bool = False


class IndexBody(BaseModel):
    path: str
    label: str
    description: str
    tags: list = []


class EvictBody(BaseModel):
    min_hits_per_week: int = 50


class ConfigBody(BaseModel):
    max_hot_paths: int = None
    hot_path_threshold: float = None
    l1_threshold: float = None
    l2_threshold: float = None
    min_hits_per_week: int = None


@router.get("/hot-paths")
async def list_hot_paths(limit: int = 70, offset: int = 0, session: AsyncSession = Depends(get_session)):
    rows = await hp.get_top_paths(session, limit=limit)
    return JSONResponse([
        {"id": str(r.id), "path": r.path, "label": r.label, "aliases": r.aliases or [],
         "hit_count": r.hit_count, "pinned": r.pinned, "last_hit_at": str(r.last_hit_at) if r.last_hit_at else None}
        for r in rows
    ])


@router.post("/hot-paths")
async def create_hot_path(body: HotPathBody, session: AsyncSession = Depends(get_session)):
    row = await hp.upsert_path(session, body.dict())
    return JSONResponse({"id": str(row.id), "path": row.path, "label": row.label})


@router.put("/hot-paths/{path_id}")
async def update_hot_path(path_id: str, body: HotPathBody, session: AsyncSession = Depends(get_session)):
    await session.execute(
        text("UPDATE nav_hot_paths SET label=:label, aliases=:aliases, pinned=:pinned, updated_at=now() WHERE id=:id"),
        {"label": body.label, "aliases": body.aliases, "pinned": body.pinned, "id": path_id}
    )
    await session.commit()
    return JSONResponse({"updated": path_id})


@router.delete("/hot-paths/{path_id}")
async def delete_hot_path(path_id: str, session: AsyncSession = Depends(get_session)):
    await session.execute(text("DELETE FROM nav_hot_paths WHERE id=:id"), {"id": path_id})
    await session.commit()
    return JSONResponse({"deleted": path_id})


@router.post("/hot-paths/{path_id}/pin")
async def pin_path(path_id: str, session: AsyncSession = Depends(get_session)):
    await session.execute(text("UPDATE nav_hot_paths SET pinned=true WHERE id=:id"), {"id": path_id})
    await session.commit()
    return JSONResponse({"pinned": path_id})


@router.post("/hot-paths/evict")
async def evict_paths(body: EvictBody, session: AsyncSession = Depends(get_session)):
    await hp.evict_cold_paths(session, body.min_hits_per_week)
    return JSONResponse({"status": "eviction complete"})


@router.get("/index")
async def list_index(limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(NavIndex).offset(offset).limit(limit))
    rows = result.scalars().all()
    return JSONResponse([
        {"id": str(r.id), "path": r.path, "label": r.label, "description": r.description, "tags": r.tags or []}
        for r in rows
    ])


@router.post("/index")
async def index_page(body: IndexBody, session: AsyncSession = Depends(get_session)):
    await emb.index_page(session, body.path, body.label, body.description, body.tags)
    return JSONResponse({"indexed": body.path})


@router.delete("/index/{index_id}")
async def delete_index(index_id: str, session: AsyncSession = Depends(get_session)):
    await session.execute(text("DELETE FROM nav_index WHERE id=:id"), {"id": index_id})
    await session.commit()
    return JSONResponse({"deleted": index_id})


@router.post("/index/reindex-all")
async def reindex_all(background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    async def _reindex(s: AsyncSession):
        result = await s.execute(select(NavIndex))
        for row in result.scalars().all():
            await emb.index_page(s, row.path, row.label, row.description, row.tags or [])

    background_tasks.add_task(_reindex, session)
    return JSONResponse({"status": "reindex started in background"})


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    since = datetime.utcnow() - timedelta(hours=24)
    result = await session.execute(
        text("SELECT layer_used, COUNT(*) as cnt, AVG(response_ms) as avg_ms FROM nav_query_log WHERE created_at >= :since GROUP BY layer_used"),
        {"since": since}
    )
    rows = result.fetchall()
    total = sum(r.cnt for r in rows)
    layer_map = {r.layer_used: {"count": r.cnt, "hit_rate": round(r.cnt / max(total, 1) * 100, 1), "avg_ms": round(float(r.avg_ms or 0), 1)} for r in rows}
    misses = await session.execute(
        text("SELECT raw_query, COUNT(*) as cnt FROM nav_query_log WHERE layer_used='MISS' AND created_at >= :since GROUP BY raw_query ORDER BY cnt DESC LIMIT 10"),
        {"since": since}
    )
    return JSONResponse({
        "total_queries_24h": total,
        "layers": layer_map,
        "top_misses": [r.raw_query for r in misses.fetchall()],
    })


@router.get("/config")
async def get_config():
    from app.core.config import settings
    return JSONResponse({
        "MAX_HOT_PATHS": settings.MAX_HOT_PATHS,
        "HOT_PATH_THRESHOLD": settings.HOT_PATH_THRESHOLD,
        "L1_THRESHOLD": settings.L1_THRESHOLD,
        "L2_THRESHOLD": settings.L2_THRESHOLD,
        "MIN_HITS_PER_WEEK": settings.MIN_HITS_PER_WEEK,
        "API_KEYS_COUNT": len(settings.api_keys_list()),
        "CORS_ORIGINS": settings.CORS_ORIGINS,
        "SERVICE_VERSION": settings.SERVICE_VERSION,
    })


@router.put("/config")
async def update_config(body: ConfigBody, session: AsyncSession = Depends(get_session)):
    from app.core.config import settings
    updates = body.dict(exclude_none=True)
    for k, v in updates.items():
        await session.execute(
            text("INSERT INTO nav_config (key, value, updated_at) VALUES (:k, :v, now()) ON CONFLICT (key) DO UPDATE SET value=:v, updated_at=now()"),
            {"k": k, "v": str(v)}
        )
        setattr(settings, k.upper(), v)
    await session.commit()
    return JSONResponse({"updated": list(updates.keys())})
