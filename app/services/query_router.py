import asyncio
import logging
import time
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

import app.services.hot_path as hot_path_service
import app.services.embedding as embedding_service
import app.services.reranker as reranker_service
from app.core.config import settings


class NavigationResult:
    def __init__(self, path, label, confidence, layer, response_ms, candidates=None, suggestion=None):
        self.path = path
        self.label = label
        self.confidence = confidence
        self.layer = layer
        self.response_ms = response_ms
        self.candidates = candidates or []
        self.suggestion = suggestion

    def dict(self):
        return {
            "path": self.path,
            "label": self.label,
            "confidence": self.confidence,
            "layer": self.layer,
            "response_ms": self.response_ms,
            "candidates": self.candidates,
            "suggestion": self.suggestion,
        }


async def route(query: str, session: AsyncSession) -> NavigationResult:
    start = time.monotonic()

    # L0: Hot path registry (fastest, ~1ms)
    r0 = await hot_path_service.lookup(query, session)
    if r0:
        ms = int((time.monotonic() - start) * 1000)
        await _log_query(session, query, r0.path, "L0", r0.confidence, ms)
        return NavigationResult(r0.path, r0.label, r0.confidence, "L0", ms)

    # L1: Embedding semantic search (~8-50ms)
    candidates = await embedding_service.search(query, session, top_k=5)
    if candidates and candidates[0].score >= settings.L1_THRESHOLD:
        top = candidates[0]
        ms = int((time.monotonic() - start) * 1000)
        await _log_query(session, query, top.path, "L1", top.score, ms)
        return NavigationResult(
            top.path, top.label, top.score, "L1", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(c.score, 4)} for c in candidates[:3]]
        )

    # L2: Cross-encoder re-ranker (~180ms, only when L1 has candidates but low confidence)
    if candidates:
        best = await reranker_service.rerank(query, candidates, session)
        if best:
            ms = int((time.monotonic() - start) * 1000)
            await _log_query(session, query, best.path, "L2", best.score, ms)
            return NavigationResult(best.path, best.label, best.score, "L2", ms)

    # MISS
    await hot_path_service.record_miss(session, query)
    ms = int((time.monotonic() - start) * 1000)
    await _log_query(session, query, None, "MISS", 0.0, ms)
    return NavigationResult(None, None, 0.0, "MISS", ms, suggestion="No navigation match found. Admin review recommended.")


async def _log_query(session: AsyncSession, query: str, path, layer: str, confidence: float, ms: int):
    try:
        await session.execute(
            text("INSERT INTO nav_query_log (id, raw_query, matched_path, layer_used, confidence, response_ms, created_at) VALUES (gen_random_uuid(), :q, :p, :l, :c, :m, now())"),
            {"q": query[:500], "p": path, "l": layer, "c": confidence, "m": ms}
        )
        await session.commit()
    except Exception as e:
        logging.error("Query log failed: %s", e)
