import json
import logging
from concurrent.futures import ThreadPoolExecutor

from services.query_router import route_query
from services.hot_path import get_top_paths

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 500
BATCH_MAX_QUERIES = 20


def _r(status, data):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(data),
    }


def handle_query(body: dict, scope: list = None, request_id: str = "-") -> dict:
    """
    Route a single navigation query through the L0→MISS cascade.

    Args:
        body:       Parsed request body; expects 'query' and optional 'context_path'.
        scope:      Site-id list from the API key.
        request_id: Lambda request ID for correlation logging.

    Returns:
        Lambda proxy response with NavigationResult fields.
    """
    query = str(body.get("query", "")).strip()
    if not query:
        return _r(400, {"error": "query field is required"})
    if len(query) > MAX_QUERY_LENGTH:
        return _r(400, {"error": f"query exceeds {MAX_QUERY_LENGTH} character limit"})
    context_path = str(body.get("context_path", "")).strip()[:500] or None
    return _r(200, route_query(query, scope, context_path=context_path,
                               request_id=request_id).to_dict())


def handle_batch(body: dict, scope: list = None, request_id: str = "-") -> dict:
    """
    Route up to BATCH_MAX_QUERIES queries concurrently.

    Args:
        body:       Parsed request body; expects 'queries' list.
        scope:      Site-id list from the API key.
        request_id: Lambda request ID for correlation logging.

    Returns:
        Lambda proxy response with list of NavigationResult fields.
    """
    queries = body.get("queries", [])
    if not isinstance(queries, list):
        return _r(400, {"error": "queries must be an array"})
    if not queries:
        return _r(400, {"error": "queries field is required"})
    if len(queries) > BATCH_MAX_QUERIES:
        return _r(400, {"error": f"Maximum {BATCH_MAX_QUERIES} queries per batch"})

    # Deduplicate: identical queries (case-insensitive, trimmed) resolve once
    # and the result is fanned back out to all original positions.
    seen: dict = {}
    unique_queries = []
    for q in queries:
        key = str(q).strip().lower()
        if key not in seen:
            seen[key] = len(unique_queries)
            unique_queries.append(str(q))
    # unique_queries preserves first-occurrence order

    def _run(q: str) -> dict:
        if len(q) > MAX_QUERY_LENGTH:
            return {"error": "query too long", "layer": "ERROR", "path": None,
                    "label": None, "confidence": 0.0, "response_ms": 0}
        return route_query(q, scope, request_id=request_id).to_dict()

    with ThreadPoolExecutor(max_workers=min(len(unique_queries), 5)) as executor:
        unique_results = list(executor.map(_run, unique_queries))

    # Fan results back out: each original query maps to its deduplicated result
    results = [unique_results[seen[str(q).strip().lower()]] for q in queries]

    return _r(200, results)


def handle_suggest(q: str, scope: list = None) -> dict:
    """
    Returns label-prefix suggestions from nav_index.
    Degrades gracefully to [] when DB is unavailable — suggest must never
    return 5xx, matching the AUTH-05 invariant that it needs no auth and
    always responds 200.
    """
    from core.db import get_conn
    scope = scope or ["default"]
    q = str(q or "").strip()[:200]  # cap before LIKE scan — unbounded q wastes DB
    results = []
    if q:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    ql = q.lower()
                    pat = f"%{ql}%"
                    # Use a savepoint so a pg_trgm failure (extension absent
                    # before migrations run) can be rolled back without aborting
                    # the whole transaction — psycopg2 marks the connection as
                    # InFailedSqlTransaction after any exception, so without
                    # ROLLBACK TO SAVEPOINT the fallback execute would also fail.
                    cur.execute("SAVEPOINT trgm_attempt")
                    try:
                        cur.execute(
                            """
                            SELECT path, label,
                                   greatest(
                                       similarity(lower(label), %s),
                                       similarity(lower(coalesce(description,'')), %s)
                                   ) AS sim
                            FROM nav_index
                            WHERE site_id = ANY(%s)
                              AND (lower(label) LIKE %s OR lower(coalesce(description,'')) LIKE %s)
                            ORDER BY (site_id = %s) DESC, sim DESC, label
                            LIMIT 5
                            """,
                            (ql, ql, scope, pat, pat, scope[0]),
                        )
                        cur.execute("RELEASE SAVEPOINT trgm_attempt")
                    except Exception:
                        # pg_trgm not yet installed — roll back to savepoint so
                        # the connection is no longer in an aborted state, then
                        # fall back to plain LIKE (sequential scan, always works).
                        cur.execute("ROLLBACK TO SAVEPOINT trgm_attempt")
                        cur.execute(
                            """
                            SELECT path, label FROM nav_index
                            WHERE site_id = ANY(%s)
                              AND (lower(label) LIKE %s OR lower(coalesce(description,'')) LIKE %s)
                            ORDER BY (site_id = %s) DESC, label LIMIT 5
                            """,
                            (scope, pat, pat, scope[0]),
                        )
                    results = [{"path": r[0], "label": r[1]} for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("suggest DB unavailable, returning []: %s", exc)
    return _r(200, results)
