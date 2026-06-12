"""Navigation cascade: intent NLU → L0 hot-path → L1 embeddings → L2 re-ranker → L3 keywords → L4 weak candidates."""
import json
import logging
import re
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

# PII patterns scrubbed from raw_query before it is written to nav_query_log.
# SA ID numbers (13 digits), email addresses, phone numbers, and payment card
# numbers are the most likely PII to appear in accidental free-text queries.
_PII_SUBS = [
    # SA ID: 13 consecutive digits OR 13 digits separated by dashes (e.g. 9001015009087 or 900101-5009-087)
    (re.compile(r'\b\d{6}[\-\s]?\d{4}[\-\s]?\d{3}\b'), '[sa-id]'),
    # Email
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'), '[email]'),
    # Phone (SA): +27 or 0 prefix
    (re.compile(r'(?<!\d)(?:\+27|0)[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)'), '[phone]'),
    # Payment card (13–16 digit, space/dash separated)
    (re.compile(r'\b(?:\d[ \-]?){13,16}\b'), '[card]'),
    # Bank account numbers: matched BEFORE policy-no so the contextual pattern
    # wins when the prefix keyword is present (e.g. "account number 12345678").
    (re.compile(r'(?i)\b(?:account|acc(?:ount)?|acct)\s*(?:no\.?|number|#)?\s*[:\-]?\s*\d{6,11}(?!\d)'), '[acct-no]'),
    # CVV: keyword "cvv"/"cvc" followed by up to 15 non-digit chars then 3-4 digits
    (re.compile(r'(?i)\b(?:cvv2?|cvc)\b[^0-9]{0,15}\d{3,4}(?!\d)'), '[cvv]'),
    # Policy numbers: 8–10 standalone digits (common Sanlam/Discovery format)
    # Runs after acct-no so "account number 12345678" uses the contextual label.
    (re.compile(r'(?<!\d)\d{8,10}(?!\d)'), '[policy-no]'),
]


def _scrub(query: str) -> str:
    """Strip obvious PII from a query string before persisting to the DB."""
    for pattern, replacement in _PII_SUBS:
        query = pattern.sub(replacement, query)
    return query


def route_query(query: str, scope: list = None, context_path: str = None,
                request_id: str = "-") -> NavigationResult:
    """
    Route a navigation query through the L0→L1→L2→L3→L4→MISS cascade.

    Args:
        query:        Raw query string from the user.
        scope:        List of site_ids to search; home site is first.
        context_path: The page the user is currently on (from widget). Used to
                      boost results semantically related to the current section,
                      so "my account" on /flights.html still resolves correctly
                      but "add bags" on /flights.html gets a stronger flight signal.
    """
    scope = scope or ["default"]
    site = scope[0]  # home site — all writes (logs, misses, learning) go here
    start = time.monotonic()

    # Resolve per-tenant threshold overrides (cold-start loaded from nav_config).
    _site_cfg = getattr(settings, "SITE_OVERRIDES", {}).get(site, {})
    _l1_threshold = _site_cfg.get("L1_THRESHOLD", settings.L1_THRESHOLD)
    _l2_threshold = _site_cfg.get("L2_THRESHOLD", settings.L2_THRESHOLD)
    _hp_threshold = _site_cfg.get("HOT_PATH_THRESHOLD", settings.HOT_PATH_THRESHOLD)

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
        _log(query, r0.path, "L0", r0.confidence, ms, site, context_path, request_id)
        return NavigationResult(r0.path, r0.label, r0.confidence, "L0", ms)

    # L1 — semantic embedding search (~8-50ms) on the intent core: question
    # scaffolding drags the vector away from the page descriptions.
    candidates = emb.search(core, top_k=5, scope=scope)

    # Context boost: if the user is already on a page, nudge candidates that
    # share its top-level path segment (e.g. /flights/ boosts other flight pages).
    # Applied as a score multiplier so it can't promote a low-confidence result
    # past the L1 threshold on its own — it only breaks ties.
    if context_path and candidates:
        ctx_seg = context_path.strip('/').split('/')[0]
        for c in candidates:
            cand_seg = c.path.strip('/').split('/')[0]
            if ctx_seg and ctx_seg == cand_seg:
                c.score = min(c.score * settings.CONTEXT_BOOST_FACTOR, 1.0)
        candidates.sort(key=lambda c: -c.score)

    if candidates and candidates[0].score >= _l1_threshold:
        top = candidates[0]
        ms = _ms(start)
        _log(query, top.path, "L1", top.score, ms, site, context_path, request_id)
        return NavigationResult(
            top.path, top.label, top.score, "L1", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(c.score, 4)} for c in candidates[:3]],
        )

    # L2 — cross-encoder re-ranker (~180ms, only when L1 has candidates but low confidence)
    if candidates:
        best = rer.rerank(core, candidates, threshold=_l2_threshold)
        if best:
            ms = _ms(start)
            _log(query, best.path, "L2", best.score, ms, site, context_path, request_id)
            return NavigationResult(best.path, best.label, best.score, "L2", ms)

    # L3 — keyword fallback against nav_index. Catches partial words ("dash")
    # and intent vocabulary the embeddings missed: the core is tokenised,
    # expanded through the domain synonym map ("log" -> "submit"), and pages
    # are ranked by token coverage. Confidence is fixed at L3_CONFIDENCE (below
    # the auto-navigate threshold) so the client always presents these as a
    # pick-list, never a silent redirect.
    like_hits = _keyword_fallback(core, scope)
    if like_hits:
        ms = _ms(start)
        conf = settings.L3_CONFIDENCE
        _log(query, like_hits[0]["path"], "L3", conf, ms, site, context_path, request_id)
        return NavigationResult(
            like_hits[0]["path"], like_hits[0]["label"], conf, "L3", ms,
            candidates=[{"path": h["path"], "label": h["label"], "score": conf} for h in like_hits],
        )

    # L4 — last resort: if L1 produced *any* candidates, surface the top 3 as
    # low-confidence suggestions instead of a dead-end MISS. Disabled by default
    # (L4_ENABLED=false) — weak guesses can lower perceived quality in portals
    # where a clean "no match" is preferable to a plausible but wrong result.
    if candidates and settings.L4_ENABLED:
        top = candidates[0]
        ms = _ms(start)
        _log(query, top.path, "L4", top.score, ms, site, context_path, request_id)
        return NavigationResult(
            top.path, top.label, min(top.score, 0.5), "L4", ms,
            candidates=[{"path": c.path, "label": c.label, "score": round(min(c.score, 0.5), 4)} for c in candidates[:3]],
        )

    # Path alias check: before declaring a full MISS, see if the query matches
    # a known old/vanity path that has been redirected in nav_path_aliases.
    # This catches post-restructure navigation gracefully without manual hot-path updates.
    alias_result = _alias_lookup(core, scope)
    if alias_result:
        ms = _ms(start)
        _log(query, alias_result["new_path"], "L0", 0.95, ms, site, context_path, request_id)
        return NavigationResult(alias_result["new_path"], alias_result["new_path"], 0.95, "L0", ms)

    # MISS — emit CloudWatch EMF metric for real-time alerting on MISS rate spikes.
    # CloudWatch EMF requires structured JSON on stdout — this is intentional,
    # NOT a debug print. The Logs agent parses it into a custom metric.
    ms = _ms(start)
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{"Namespace": "portal-nav-api", "Dimensions": [["site"]], "Metrics": [{"Name": "Miss", "Unit": "Count"}]}],
        },
        "site": site,
        "Miss": 1,
        "request_id": request_id,
    }))
    _log(query, None, "MISS", 0.0, ms, site, context_path, request_id)
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


def _alias_lookup(core: str, scope: list) -> Optional[dict]:
    """Check nav_path_aliases for a redirect matching the query core.

    Strips leading slash and checks both the raw core and cleaned path form
    so "old dashboard" and "/old-dashboard" both resolve.
    Returns {"new_path": str} or None.
    """
    # Normalise: replace spaces with dashes, strip punctuation for path matching
    slug = re.sub(r'[^a-z0-9/\-]', '', core.lower().replace(' ', '-')).strip('-')
    candidates_to_try = list({core.lower().strip(), '/' + slug, slug})
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT new_path FROM nav_path_aliases "
                    "WHERE site_id = ANY(%s) AND lower(old_path) = ANY(%s) LIMIT 1",
                    (scope, candidates_to_try),
                )
                row = cur.fetchone()
        return {"new_path": row[0]} if row else None
    except Exception as e:
        logger.warning("alias lookup failed: %s", e)
        return None


def _log(query: str, path: Optional[str], layer: str, confidence: float, ms: int,
         site: str = "default", context_path: Optional[str] = None,
         request_id: str = "-"):
    safe_query = _scrub(query)[:500]
    safe_context = (_scrub(context_path)[:500] if context_path else None)
    logger.info(json.dumps({
        "event": "nav_query",
        "layer": layer,
        "site": site,
        "confidence": round(confidence, 4),
        "response_ms": ms,
        "request_id": request_id,
    }))
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO nav_query_log "
                    "(raw_query,matched_path,layer_used,confidence,response_ms,site_id,context_path) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (safe_query, path, layer, confidence, ms, site, safe_context),
                )
            conn.commit()
    except Exception as e:
        logger.warning("query log failed: %s", e)
