import json
from services.query_router import route_query
from services.hot_path import get_top_paths


def _r(status, data):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data)}


def handle_query(body: dict, scope: list = None, request_id: str = "-"):
    query = str(body.get("query", "")).strip()
    if not query:
        return _r(400, {"error": "query field is required"})
    context_path = str(body.get("context_path", "")).strip() or None
    return _r(200, route_query(query, scope, context_path=context_path,
                               request_id=request_id).to_dict())


def handle_batch(body: dict, scope: list = None, request_id: str = "-"):
    queries = body.get("queries", [])
    if not queries:
        return _r(400, {"error": "queries field is required"})
    if len(queries) > 20:
        return _r(400, {"error": "Maximum 20 queries per batch"})
    return _r(200, [route_query(str(q), scope, request_id=request_id).to_dict()
                    for q in queries])


def handle_suggest(q: str, scope: list = None):
    """
    Returns label-prefix suggestions from nav_index.
    Degrades gracefully to [] when DB is unavailable — suggest must never
    return 5xx, matching the AUTH-05 invariant that it needs no auth and
    always responds 200.
    """
    import logging
    from core.db import get_conn
    scope = scope or ["default"]
    results = []
    if q:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT path, label FROM nav_index
                        WHERE site_id = ANY(%s)
                          AND (lower(label) LIKE %s OR lower(description) LIKE %s)
                        ORDER BY (site_id = %s) DESC, label LIMIT 5
                        """,
                        (scope, f"%{q.lower()}%", f"%{q.lower()}%", scope[0]),
                    )
                    results = [{"path": r[0], "label": r[1]} for r in cur.fetchall()]
        except Exception as e:
            logging.getLogger(__name__).warning("suggest DB unavailable, returning []: %s", e)
    return _r(200, results)
