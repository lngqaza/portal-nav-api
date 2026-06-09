"""Admin route handlers — CRUD for hot-paths, index, stats, config."""
import json
from datetime import datetime, timedelta

from core.db import get_conn
from core.config import settings
from services.hot_path import get_top_paths, upsert_path, evict_cold_paths
from services.embedding import index_page


def _r(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data, default=str),
    }


def handle_admin(path: str, method: str, body: dict, params: dict):

    # ── Hot paths ───────────────────────────────────────────────────────────
    if path == "/admin/hot-paths" and method == "GET":
        return _r(200, get_top_paths(int(params.get("limit", 70))))

    if path == "/admin/hot-paths" and method == "POST":
        return _r(200, upsert_path(body))

    if path.startswith("/admin/hot-paths/") and not path.endswith("/pin"):
        pid = path.split("/")[-1]
        if method == "PUT":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE nav_hot_paths SET label=%s,aliases=%s,pinned=%s,updated_at=now() WHERE id=%s",
                        (body.get("label"), body.get("aliases", []), body.get("pinned", False), pid),
                    )
                conn.commit()
            return _r(200, {"updated": pid})
        if method == "DELETE":
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nav_hot_paths WHERE id=%s", (pid,))
                conn.commit()
            return _r(200, {"deleted": pid})

    if path.startswith("/admin/hot-paths/") and path.endswith("/pin") and method == "POST":
        pid = path.split("/")[-2]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE nav_hot_paths SET pinned=true WHERE id=%s", (pid,))
            conn.commit()
        return _r(200, {"pinned": pid})

    if path == "/admin/hot-paths/evict" and method == "POST":
        return _r(200, {"evicted": evict_cold_paths(int(body.get("min_hits_per_week", 50)))})

    # ── Index ────────────────────────────────────────────────────────────────
    if path == "/admin/index" and method == "GET":
        limit, offset = int(params.get("limit", 50)), int(params.get("offset", 0))
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id,path,label,description,tags FROM nav_index LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return _r(200, rows)

    if path == "/admin/index" and method == "POST":
        index_page(body["path"], body["label"], body.get("description", ""), body.get("tags", []))
        return _r(200, {"indexed": body["path"]})

    if path.startswith("/admin/index/") and method == "DELETE":
        iid = path.split("/")[-1]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM nav_index WHERE id=%s", (iid,))
            conn.commit()
        return _r(200, {"deleted": iid})

    if path == "/admin/index/reindex-all" and method == "POST":
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT path,label,description,tags FROM nav_index")
                rows = cur.fetchall()
        for row in rows:
            index_page(row[0], row[1], row[2] or "", row[3] or [])
        return _r(200, {"reindexed": len(rows)})

    # ── Stats ────────────────────────────────────────────────────────────────
    if path == "/admin/stats" and method == "GET":
        since = datetime.utcnow() - timedelta(hours=24)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT layer_used,COUNT(*),AVG(response_ms) FROM nav_query_log WHERE created_at>=%s GROUP BY layer_used",
                    (since,),
                )
                layer_rows = cur.fetchall()
                total = sum(r[1] for r in layer_rows)
                layers = {
                    r[0]: {"count": r[1], "hit_rate": round(r[1]/max(total,1)*100,1), "avg_ms": round(float(r[2] or 0),1)}
                    for r in layer_rows
                }
                cur.execute(
                    "SELECT raw_query,COUNT(*) FROM nav_query_log WHERE layer_used='MISS' AND created_at>=%s GROUP BY raw_query ORDER BY 2 DESC LIMIT 10",
                    (since,),
                )
                top_misses = [r[0] for r in cur.fetchall()]
        return _r(200, {"total_queries_24h": total, "layers": layers, "top_misses": top_misses})

    # ── Config ───────────────────────────────────────────────────────────────
    if path == "/admin/config" and method == "GET":
        return _r(200, {
            "MAX_HOT_PATHS": settings.MAX_HOT_PATHS,
            "HOT_PATH_THRESHOLD": settings.HOT_PATH_THRESHOLD,
            "L1_THRESHOLD": settings.L1_THRESHOLD,
            "L2_THRESHOLD": settings.L2_THRESHOLD,
            "SERVICE_VERSION": settings.SERVICE_VERSION,
            "API_KEYS_COUNT": len(settings.API_KEYS),
        })

    if path == "/admin/config" and method == "PUT":
        mapping = {"MAX_HOT_PATHS": int, "HOT_PATH_THRESHOLD": float, "L1_THRESHOLD": float, "L2_THRESHOLD": float}
        updated = {}
        for k, cast in mapping.items():
            val = body.get(k) or body.get(k.lower())
            if val is not None:
                setattr(settings, k, cast(val))
                updated[k] = cast(val)
        return _r(200, {"updated": updated})

    return _r(404, {"error": f"Unknown admin route: {method} {path}"})
