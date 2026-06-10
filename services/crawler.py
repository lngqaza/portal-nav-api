"""
Sitemap crawler — fetches a sitemap.xml and bulk-indexes all discovered pages.

Supports:
  - Standard sitemaps (<urlset>)
  - Sitemap index files (<sitemapindex>) — follows one level of child sitemaps
  - News/image/video sitemaps (extra tags ignored, <loc> and <title> extracted)

Each discovered URL is indexed via services.embedding.index_page so it gets
a pgvector embedding immediately — no separate reindex step needed.

Network access: Lambda must have outbound internet access (NAT gateway or VPC
endpoint) to reach external sitemaps.  Internal sitemaps (same VPC) always work.
"""
import logging
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Generator

from services.embedding import index_page

logger = logging.getLogger(__name__)

# Max pages to index in a single crawl call — prevents Lambda timeout
MAX_PAGES_PER_CRAWL = 200
REQUEST_TIMEOUT_S   = 8


def crawl_sitemap(sitemap_url: str, base_label_prefix: str = "") -> dict:
    """
    Fetch `sitemap_url`, parse all <loc> entries, and index each page.

    If the URL points to a <sitemapindex>, child sitemaps are followed one
    level deep.  Processing stops at MAX_PAGES_PER_CRAWL to stay within
    Lambda's 60-second timeout.

    Args:
        sitemap_url:       Fully-qualified URL of the sitemap.xml to crawl.
        base_label_prefix: Optional prefix prepended to derived page labels
                           (e.g. "Portal - ").

    Returns:
        dict with keys: indexed (int), skipped (int), errors (list[str]).
    """
    indexed, skipped, errors = 0, 0, []

    try:
        pages = list(_iter_pages(sitemap_url))
    except Exception as exc:
        return {"indexed": 0, "skipped": 0, "errors": [str(exc)]}

    for page in pages[:MAX_PAGES_PER_CRAWL]:
        label = (base_label_prefix + page["label"]).strip() or _path_to_label(page["url"])
        try:
            index_page(
                path=_url_to_path(page["url"]),
                label=label,
                description=page.get("description", ""),
                tags=page.get("tags", []),
            )
            indexed += 1
        except Exception as exc:
            errors.append(f"{page['url']}: {exc}")
            skipped += 1

    if len(pages) > MAX_PAGES_PER_CRAWL:
        skipped += len(pages) - MAX_PAGES_PER_CRAWL
        errors.append(
            f"Truncated at {MAX_PAGES_PER_CRAWL} pages "
            f"({len(pages) - MAX_PAGES_PER_CRAWL} skipped — call again with offset)"
        )

    return {"indexed": indexed, "skipped": skipped, "errors": errors}


def bulk_index(pages: list) -> dict:
    """
    Index a list of page dicts in one call.

    Each dict must have `path` and `label`; `description` and `tags` are optional.

    Args:
        pages: List of dicts with keys path (str), label (str),
               description (str, optional), tags (list, optional).

    Returns:
        dict with keys: indexed (int), skipped (int), errors (list[str]).
    """
    indexed, skipped, errors = 0, 0, []
    for page in pages[:MAX_PAGES_PER_CRAWL]:
        if not page.get("path") or not page.get("label"):
            errors.append(f"Missing path or label: {page}")
            skipped += 1
            continue
        try:
            index_page(
                path=page["path"],
                label=page["label"],
                description=page.get("description", ""),
                tags=page.get("tags", []),
            )
            indexed += 1
        except Exception as exc:
            errors.append(f"{page['path']}: {exc}")
            skipped += 1
    return {"indexed": indexed, "skipped": skipped, "errors": errors}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _fetch_xml(url: str) -> ET.Element:
    """Fetch URL and parse as XML. Raises on HTTP error or parse failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "portal-nav-crawler/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            content = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc
    return ET.fromstring(content)


def _iter_pages(sitemap_url: str) -> Generator[dict, None, None]:
    """
    Yield page dicts from a sitemap URL.
    Follows one level of <sitemapindex> child links.
    """
    root = _fetch_xml(sitemap_url)
    # Strip XML namespace for simpler tag matching
    tag = root.tag.split("}")[1] if "}" in root.tag else root.tag

    if tag == "sitemapindex":
        # Index file — follow each child sitemap
        ns = {"sm": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
        loc_tag = "{%s}loc" % ns.get("sm", "") if ns else "loc"
        for sitemap_el in root:
            loc = sitemap_el.find(loc_tag)
            if loc is not None and loc.text:
                try:
                    yield from _iter_pages(loc.text.strip())
                except Exception as exc:
                    logger.warning("child sitemap error %s: %s", loc.text, exc)
    else:
        # Standard urlset
        yield from _parse_urlset(root)


def _parse_urlset(root: ET.Element) -> Generator[dict, None, None]:
    """Parse a <urlset> element and yield page dicts."""
    ns_prefix = ""
    if "}" in root.tag:
        ns_prefix = root.tag.split("}")[0].lstrip("{")

    def _tag(name):
        return "{%s}%s" % (ns_prefix, name) if ns_prefix else name

    for url_el in root:
        loc = url_el.find(_tag("loc"))
        if loc is None or not loc.text:
            continue

        url = loc.text.strip()

        # Try to extract a title from news/image/video sitemap extensions
        title = None
        for child in url_el:
            # <news:news><news:title> or <image:image><image:title>
            for grandchild in child:
                local = grandchild.tag.split("}")[-1]
                if local == "title" and grandchild.text:
                    title = grandchild.text.strip()
                    break
            if title:
                break

        label = title or _path_to_label(url)
        yield {"url": url, "label": label, "description": "", "tags": []}


def _url_to_path(url: str) -> str:
    """Extract the path component from a URL. Returns '/' if none."""
    # Remove scheme + host; keep path + query
    match = re.match(r"https?://[^/]+(/.*)$", url)
    if match:
        path = match.group(1).split("?")[0].split("#")[0]
        return path or "/"
    return url if url.startswith("/") else "/" + url


def _path_to_label(url_or_path: str) -> str:
    """
    Derive a human-readable label from a URL or path.
    e.g. '/claims/submit-new' → 'Claims Submit New'
    """
    path = _url_to_path(url_or_path)
    # Take the last non-empty segment
    segments = [s for s in path.rstrip("/").split("/") if s]
    if not segments:
        return "Home"
    label = segments[-1].replace("-", " ").replace("_", " ")
    return label.title()
