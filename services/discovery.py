"""Self-discovery — pages index themselves as visitors browse.

The widget extracts the page's own DOM content (title, headings, button
text) and POSTs it to /discover. New pages are indexed immediately;
re-visits are deduped with a content hash so re-embedding only happens
when the page actually changed. This replaces manual seeding and works
where the crawler can't (the Lambda has no outbound internet).
"""
import hashlib
import logging
import re
import urllib.parse

from core.db import get_conn
from services.embedding import index_page

logger = logging.getLogger(__name__)

MAX_LABEL_LEN = 120
MAX_DESC_LEN = 400
MAX_TAGS = 12
MAX_TAG_LEN = 40


def _clean(s: str, max_len: int) -> str:
    """Collapse whitespace and cap length."""
    return re.sub(r"\s+", " ", str(s or "")).strip()[:max_len]


def sanitise(body: dict) -> dict:
    """Validate and normalise a discovery payload from the widget.

    Returns {path, label, description, tags} or raises ValueError.
    """
    path = _clean(body.get("path"), 500)
    # Decode percent-encoding before the traversal check so %2e%2e bypasses are caught.
    decoded = urllib.parse.unquote(path)
    if not decoded.startswith("/") or ".." in decoded:
        raise ValueError("path must be an absolute portal path")
    # Strip query/fragment so variants of one page collapse to one row
    path = path.split("?")[0].split("#")[0] or "/"

    label = _clean(body.get("label"), MAX_LABEL_LEN)
    if not label:
        raise ValueError("label is required")

    description = _clean(body.get("description"), MAX_DESC_LEN)
    tags = []
    for t in (body.get("tags") or [])[:MAX_TAGS]:
        t = _clean(t, MAX_TAG_LEN).lower()
        if t and t not in tags:
            tags.append(t)
    return {"path": path, "label": label, "description": description, "tags": tags}


def content_hash(page: dict) -> str:
    """Stable hash of the indexable content — changes only when content does."""
    blob = "|".join([page["label"], page["description"], " ".join(page["tags"])])
    return hashlib.sha256(blob.encode()).hexdigest()


def discover_page(body: dict, site: str = "default") -> dict:
    """Index a self-reported page if it is new or its content changed.

    Returns {indexed: bool, reason: str}.
    """
    page = sanitise(body)
    h = content_hash(page)
    row = None  # initialise before try so the final log line never raises NameError
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT content_hash FROM nav_index WHERE site_id = %s AND path = %s", (site, page["path"]))
                row = cur.fetchone()
        if row and row[0] == h:
            return {"indexed": False, "reason": "unchanged"}
    except Exception as e:
        logger.warning("discover hash check failed (indexing anyway): %s", e)

    # index_page embeds and upserts label/description/tags
    index_page(page["path"], page["label"], page["description"], page["tags"], site)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE nav_index SET content_hash = %s WHERE site_id = %s AND path = %s",
                    (h, site, page["path"]),
                )
            conn.commit()
    except Exception as e:
        logger.warning("discover hash store failed: %s", e)

    logger.info("discovered %s (%s)", page["path"], "new" if not row else "updated")
    return {"indexed": True, "reason": "new" if not row else "updated"}
