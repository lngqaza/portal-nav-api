import json
from services.query_router import route_query
from services.hot_path import get_top_paths


def _r(status, data):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data)}


def handle_query(body: dict):
    query = str(body.get("query", "")).strip()
    if not query:
        return _r(400, {"error": "query field is required"})
    return _r(200, route_query(query).to_dict())


def handle_batch(body: dict):
    queries = body.get("queries", [])
    if not queries:
        return _r(400, {"error": "queries field is required"})
    if len(queries) > 20:
        return _r(400, {"error": "Maximum 20 queries per batch"})
    return _r(200, [route_query(str(q)).to_dict() for q in queries])


def handle_suggest(q: str):
    from core.db import get_conn
    # Search both nav_index labels and hot_path labels
    results = []
    if q:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT path, label FROM nav_index
                    WHERE lower(label) LIKE %s OR lower(description) LIKE %s
                    ORDER BY label LIMIT 5
                    """,
                    (f"%{q.lower()}%", f"%{q.lower()}%"),
                )
                results = [{"path": r[0], "label": r[1]} for r in cur.fetchall()]
    return _r(200, results)
