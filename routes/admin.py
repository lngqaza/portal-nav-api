"""Admin route handlers — CRUD for hot-paths, index, stats, config."""
import ipaddress
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from core.db import get_conn
from core.config import settings
from services.hot_path import get_top_paths, upsert_path, evict_cold_paths
from services.embedding import index_page
from services.crawler import crawl_sitemap, bulk_index
from services.feedback import get_navigation_stats
from services.analytics import get_analytics
from services.miss_mining import get_miss_report

_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
_BLOCKED_HOSTS = frozenset([
    '169.254.169.254', 'metadata.google.internal',
    'instance-data', 'localhost', '0.0.0.0',
])


def _validate_uuid(value: str, field: str = "id") -> str:
    """Raise ValueError if value is not a valid UUID; return it if valid."""
    if not _UUID_RE.match(value or ""):
        raise ValueError(f"Invalid {field}: {value!r}")
    return value


def _safe_int(value, default: int) -> int:
    """Parse value as int, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validate_sitemap_url(url: str) -> None:
    """Raise ValueError if url is not a safe public HTTPS URL.

    Blocks RFC-1918 addresses, loopback, link-local, and known cloud metadata
    endpoints to prevent SSRF attacks. Admin token auth is not sufficient alone
    because a compromised admin token would allow credential exfil via crawl.
    """
    if not url.lower().startswith('https://'):
        raise ValueError("sitemap_url must use HTTPS")
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValueError("sitemap_url is not a valid URL")
    host = (parsed.hostname or '').lower()
    if not host:
        raise ValueError("sitemap_url has no hostname")
    if host in _BLOCKED_HOSTS:
        raise ValueError(f"sitemap_url hostname not permitted: {host!r}")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"sitemap_url resolves to a reserved IP: {host!r}")
    except ValueError as exc:
        if any(w in str(exc) for w in ('private', 'loopback', 'link_local', 'reserved', 'permitted')):
            raise
        # Not an IP literal — hostname check passed


def _r(status, data):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(data, default=str),
    }


def handle_admin(path: str, method: str, body: dict, params: dict):

    # ── Hot paths ───────────────────────────────────────────────────────────
    if path == "/admin/hot-paths" and method == "GET":
        site = params.get("site") or None
        return _r(200, get_top_paths(_safe_int(params.get("limit", 70), 70), site=site))

    if path == "/admin/hot-paths" and method == "POST":
        return _r(200, upsert_path(body))

    if path.startswith("/admin/hot-paths/") and not path.endswith("/pin"):
        pid = _validate_uuid(path.split("/")[-1])
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
        pid = _validate_uuid(path.split("/")[-2])
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE nav_hot_paths SET pinned=true WHERE id=%s", (pid,))
            conn.commit()
        return _r(200, {"pinned": pid})

    if path == "/admin/hot-paths/evict" and method == "POST":
        site = body.get("site") or None
        return _r(200, {"evicted": evict_cold_paths(_safe_int(body.get("min_hits_per_week", 50), 50), site=site)})

    # ── Index ────────────────────────────────────────────────────────────────
    if path == "/admin/index" and method == "GET":
        limit  = _safe_int(params.get("limit", 50), 50)
        offset = _safe_int(params.get("offset", 0), 0)
        site   = params.get("site") or None
        with get_conn() as conn:
            with conn.cursor() as cur:
                if site:
                    cur.execute(
                        "SELECT id,path,label,description,tags FROM nav_index "
                        "WHERE site_id=%s LIMIT %s OFFSET %s",
                        (site, limit, offset),
                    )
                else:
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
        iid = _validate_uuid(path.split("/")[-1])
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
        since = datetime.now(timezone.utc) - timedelta(hours=24)
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
                cast_val = cast(val)
                setattr(settings, k, cast_val)
                updated[k] = cast_val
        # Persist to nav_config so changes survive Lambda cold starts.
        if updated:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    for k, v in updated.items():
                        cur.execute(
                            """
                            INSERT INTO nav_config (key, value, updated_at)
                            VALUES (%s, %s, now())
                            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                            """,
                            (k, str(v)),
                        )
                conn.commit()
        return _r(200, {"updated": updated})

    # ── Bulk index ───────────────────────────────────────────────────────────
    # POST /admin/index/bulk  { "pages": [{ path, label, description?, tags? }] }
    if path == "/admin/index/bulk" and method == "POST":
        pages = body.get("pages", [])
        if not pages or not isinstance(pages, list):
            return _r(400, {"error": "pages array is required"})
        return _r(200, bulk_index(pages))

    # ── Sitemap crawl ────────────────────────────────────────────────────────
    # POST /admin/index/crawl  { "sitemap_url": "https://...", "label_prefix": "" }
    if path == "/admin/index/crawl" and method == "POST":
        sitemap_url = body.get("sitemap_url", "").strip()
        if not sitemap_url:
            return _r(400, {"error": "sitemap_url is required"})
        try:
            _validate_sitemap_url(sitemap_url)
        except ValueError as exc:
            return _r(400, {"error": str(exc)})
        result = crawl_sitemap(sitemap_url, body.get("label_prefix", ""))
        return _r(200, result)

    # ── Navigation feedback stats ─────────────────────────────────────────────
    # GET /admin/feedback?days=7
    if path == "/admin/feedback" and method == "GET":
        days = _safe_int(params.get("days", 7), 7)
        site = params.get("site") or None
        return _r(200, get_navigation_stats(days, site))

    # ── Analytics — CTR, daily volume, layer breakdown, top queries/pages ─────
    # GET /admin/analytics?days=7&site=lumo
    if path == "/admin/analytics" and method == "GET":
        days = _safe_int(params.get("days", 7), 7)
        site = params.get("site") or None
        return _r(200, get_analytics(days, site))

    # ── Miss-mining report ────────────────────────────────────────────────────
    # GET /admin/miss-report?days=7&site=lumo
    if path == "/admin/miss-report" and method == "GET":
        days = _safe_int(params.get("days", 7), 7)
        site = params.get("site") or None
        return _r(200, get_miss_report(days, site))

    return _r(404, {"error": f"Unknown admin route: {method} {path}"})
