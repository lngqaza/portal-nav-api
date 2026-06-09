"""3-layer navigation cascade: L0 hot-path → L1 embeddings → L2 re-ranker."""
import logging
import time
from typing import Optional

from core.config import settings
from core.db import get_conn
from models.navigation import NavigationResult
from services import hot_path as hp
from services import embedding as emb
from services import reranker as rer

logger = logging.getLogger(__name__)


def route_query(query: str) -> NavigationResult:
    start = time.monotonic()

    # L0 — hot path registry (~1ms)
    r0 = hp.lookup(query)
    if r0:
        ms = _ms(start)
        _log(query, r0.path, "L0", r0.confidence, ms)
        return NavigationResult(r0.path, r0.label, r0.confidence, "L0", ms)

    # L1 — semantic embedding search (~8-50ms)
    candidates = emb.search(query, top_k=5)
    if candidates and candidates[0].score >= settings.L1_THRESHOLD:
        top = candidates[0]
        ms = _ms(start)
        _log(query, top.path, "L1", top.score, ms)
        return NavigationResult(
            top.path, top.label, top.score, "L1", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(c.score, 4)} for c in candidates[:3]],
        )

    # L2 — cross-encoder re-ranker (~180ms, only when L1 has candidates but low confidence)
    if candidates:
        best = rer.rerank(query, candidates)
        if best:
            ms = _ms(start)
            _log(query, best.path, "L2", best.score, ms)
            return NavigationResult(best.path, best.label, best.score, "L2", ms)

    # MISS
    hp.record_miss(query)
    ms = _ms(start)
    _log(query, None, "MISS", 0.0, ms)
    return NavigationResult(None, None, 0.0, "MISS", ms, suggestion="No match found")


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _log(query: str, path: Optional[str], layer: str, confidence: float, ms: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO nav_query_log (raw_query,matched_path,layer_used,confidence,response_ms) VALUES (%s,%s,%s,%s,%s)",
                    (query[:500], path, layer, confidence, ms),
                )
            conn.commit()
    except Exception as e:
        logger.warning("query log failed: %s", e)
