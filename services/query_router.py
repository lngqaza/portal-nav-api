"""Navigation cascade: intent NLU → L0 hot-path → L1 embeddings → L2 re-ranker → L3 keywords → L4 weak candidates."""
import logging
import time
from typing import Optional

from core.config import settings
from core.db import get_conn
from models.navigation import NavigationResult
from services import hot_path as hp
from services import embedding as emb
from services import intent
from services import reranker as rer
from services import spelling

logger = logging.getLogger(__name__)


def route_query(query: str, scope: list = None) -> NavigationResult:
    scope = scope or ["default"]
    site = scope[0]  # home site — all writes (logs, misses, learning) go here
    start = time.monotonic()

    # NLU preprocessing — reduce conversational questions to their intent
    # core so every layer matches meaning, not phrasing, then snap typos to
    # the searchable vocabulary:
    # "where do I log a claim?" -> "log a claim"; "paymnet" -> "payment"
    core = spelling.correct_query(intent.intent_core(query), site)

    # L0 — hot path registry (~1ms). Try the raw query first (aliases may be
    # full phrases), then the intent core if stripping changed anything.
    r0 = hp.lookup(query, scope)
    if not r0 and core != query.lower().strip():
        r0 = hp.lookup(core, scope)
    if r0:
        ms = _ms(start)
        _log(query, r0.path, "L0", r0.confidence, ms, site)
        return NavigationResult(r0.path, r0.label, r0.confidence, "L0", ms)

    # L1 — semantic embedding search (~8-50ms) on the intent core: question
    # scaffolding drags the vector away from the page descriptions.
    candidates = emb.search(core, top_k=5, scope=scope)
    if candidates and candidates[0].score >= settings.L1_THRESHOLD:
        top = candidates[0]
        ms = _ms(start)
        _log(query, top.path, "L1", top.score, ms, site)
        return NavigationResult(
            top.path, top.label, top.score, "L1", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(c.score, 4)} for c in candidates[:3]],
        )

    # L2 — cross-encoder re-ranker (~180ms, only when L1 has candidates but low confidence)
    if candidates:
        best = rer.rerank(core, candidates)
        if best:
            ms = _ms(start)
            _log(query, best.path, "L2", best.score, ms, site)
            return NavigationResult(best.path, best.label, best.score, "L2", ms)

    # L3 — keyword fallback against nav_index. Catches partial words ("dash")
    # and intent vocabulary the embeddings missed: the core is tokenised,
    # expanded through the domain synonym map ("log" -> "submit"), and pages
    # are ranked by token coverage. Confidence is fixed below the
    # auto-navigate threshold so the client always presents these as a
    # pick-list, never a silent redirect.
    like_hits = _keyword_fallback(core, scope)
    if like_hits:
        ms = _ms(start)
        _log(query, like_hits[0]["path"], "L3", 0.5, ms, site)
        return NavigationResult(
            like_hits[0]["path"], like_hits[0]["label"], 0.5, "L3", ms,
            candidates=[{"path": h["path"], "label": h["label"], "score": 0.5} for h in like_hits],
        )

    # L4 — last resort: if L1 produced *any* candidates, surface the top 3 as
    # low-confidence suggestions instead of a dead-end MISS. A weak guess the
    # user can confirm beats "no match" for conversational queries.
    if candidates:
        top = candidates[0]
        ms = _ms(start)
        _log(query, top.path, "L4", top.score, ms, site)
        return NavigationResult(
            top.path, top.label, min(top.score, 0.5), "L4", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(min(c.score, 0.5), 4)} for c in candidates[:3]],
        )

    # MISS
    hp.record_miss(query, site)
    ms = _ms(start)
    _log(query, None, "MISS", 0.0, ms, site)
    return NavigationResult(None, None, 0.0, "MISS", ms, suggestion="No match found")


def _keyword_fallback(core: str, scope: list) -> list:
    """Keyword match on nav_index label/description/tags.

    Terms = whole core as a substring (handles partial words like "dash")
    plus synonym-expanded tokens. Pages are ranked by term coverage with
    label hits weighing double. Returns up to 5 {path,label} dicts; [] on
    no match or DB failure — a fallback layer must never turn a MISS into
    a 5xx.
    """
    terms = []
    whole = core.strip()
    if whole:
        terms.append(whole)
    for t in intent.expanded_tokens(core):
        if t not in terms:
            terms.append(t)
    if not terms:
        return []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                conditions = " OR ".join(
                    ["(lower(label) LIKE %s OR lower(coalesce(description,'')) LIKE %s"
                     " OR lower(coalesce(array_to_string(tags,' '),'')) LIKE %s)"] * len(terms)
                )
                params = []
                for t in terms:
                    params += [f"%{t}%"] * 3
                params.insert(0, scope)
                cur.execute(
                    f"""
                    SELECT path, label, lower(label),
                           lower(coalesce(description,'') || ' ' || coalesce(array_to_string(tags,' '),'')),
                           site_id
                    FROM nav_index WHERE site_id = ANY(%s) AND ({conditions})
                    """,
                    params,
                )
                rows = cur.fetchall()
        scored = []
        for path, label, llabel, lbody, row_site in rows:
            score = sum((2 if t in llabel else 0) + (1 if t in lbody else 0) for t in terms)
            if row_site != scope[0]:
                score -= 0.5  # home-site pages outrank shared/sibling pages on ties
            scored.append((score, label, path))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [{"path": p, "label": l} for _, l, p in scored[:5]]
    except Exception as e:
        logger.warning("L3 keyword fallback failed: %s", e)
        return []


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _log(query: str, path: Optional[str], layer: str, confidence: float, ms: int, site: str = "default"):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO nav_query_log (raw_query,matched_path,layer_used,confidence,response_ms,site_id) VALUES (%s,%s,%s,%s,%s,%s)",
                    (query[:500], path, layer, confidence, ms, site),
                )
            conn.commit()
    except Exception as e:
        logger.warning("query log failed: %s", e)
