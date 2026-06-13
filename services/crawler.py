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
import ipaddress
import logging
import re
import urllib.parse
import urllib.request
import urllib.error
from typing import Generator

_BLOCKED_HOSTS = frozenset([
    '169.254.169.254', 'metadata.google.internal',
    'instance-data', 'localhost', '0.0.0.0', '127.0.0.1',
])


def validate_sitemap_url(url: str) -> None:
    """Raise ValueError if url is not a safe public HTTPS URL.

    Blocks RFC-1918 addresses, loopback, link-local, and known cloud metadata
    endpoints to prevent SSRF. Called from both the admin route handler (for the
    top-level URL) and the crawler itself (for child sitemapindex URLs).
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

# defusedxml prevents XXE and billion-laughs attacks. Hard-fail at import time
# so a missing dependency surfaces immediately at cold start rather than
# silently degrading to the vulnerable stdlib parser.
import defusedxml.ElementTree as ET
import xml.etree.ElementTree as _StdET  # Element type annotation only

from services.embedding import index_page

logger = logging.getLogger(__name__)

# Max pages to index in a single crawl call — prevents Lambda timeout
MAX_PAGES_PER_CRAWL = 200
REQUEST_TIMEOUT_S   = 8


def crawl_sitemap(sitemap_url: str, base_label_prefix: str = "", site: str = "default") -> dict:
    """
    Fetch `sitemap_url`, parse all <loc> entries, and index each page.

    If the URL points to a <sitemapindex>, child sitemaps are followed one
    level deep.  Processing stops at MAX_PAGES_PER_CRAWL to stay within
    Lambda's 60-second timeout.

    Args:
        sitemap_url:       Fully-qualified URL of the sitemap.xml to crawl.
        base_label_prefix: Optional prefix prepended to derived page labels.
        site:              Tenant site_id to index pages under. Defaults to "default".

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
                site=site,
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


def bulk_index(pages: list, site: str = "default") -> dict:
    """
    Index a list of page dicts in one call.

    Each dict must have `path` and `label`; `description` and `tags` are optional.

    Args:
        pages: List of dicts with keys path (str), label (str),
               description (str, optional), tags (list, optional).
        site:  Tenant site_id. Defaults to "default".

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
                site=site,
            )
            indexed += 1
        except Exception as exc:
            errors.append(f"{page['path']}: {exc}")
            skipped += 1
    return {"indexed": indexed, "skipped": skipped, "errors": errors}


# ── Internal helpers ─────────────────────────────────────────────────────────

class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Raise on any HTTP redirect so SSRF bypass via open-redirect is impossible.

    urlopen() follows redirects by default. An attacker can host a public URL
    that issues a 301 to 169.254.169.254 — validate_sitemap_url() checks only
    the original URL, so the redirect destination is never validated.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError(f"Redirect to {newurl!r} blocked (SSRF protection)")


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)

# Cap sitemap response size to prevent OOM from attacker-hosted multi-GB files.
_MAX_SITEMAP_BYTES = 10 * 1024 * 1024  # 10 MB


def _fetch_xml(url: str) -> _StdET.Element:
    """Fetch URL and parse as XML. Raises on HTTP error, redirect, or parse failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "portal-nav-crawler/1.0"})
    try:
        with _NO_REDIRECT_OPENER.open(req, timeout=REQUEST_TIMEOUT_S) as resp:
            content = resp.read(_MAX_SITEMAP_BYTES)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc
    return ET.fromstring(content)


_MAX_SITEMAP_DEPTH = 1  # follow sitemapindex → child, but not child → grandchild


def _iter_pages(sitemap_url: str, _depth: int = 0) -> Generator[dict, None, None]:
    """
    Yield page dicts from a sitemap URL.
    Follows <sitemapindex> child links up to _MAX_SITEMAP_DEPTH levels deep.
    """
    root = _fetch_xml(sitemap_url)
    # Strip XML namespace for simpler tag matching
    tag = root.tag.split("}")[1] if "}" in root.tag else root.tag

    if tag == "sitemapindex":
        if _depth >= _MAX_SITEMAP_DEPTH:
            logger.warning(
                "Sitemap recursion limit reached at %s (depth %d) — skipping children",
                sitemap_url, _depth,
            )
            return
        # Index file — follow each child sitemap
        ns = {"sm": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
        loc_tag = "{%s}loc" % ns.get("sm", "") if ns else "loc"
        for sitemap_el in root:
            loc = sitemap_el.find(loc_tag)
            if loc is not None and loc.text:
                child_url = loc.text.strip()
                try:
                    validate_sitemap_url(child_url)  # SSRF guard on child URLs
                    yield from _iter_pages(child_url, _depth=_depth + 1)
                except (ValueError, Exception) as exc:
                    logger.warning("child sitemap error %s: %s", child_url, exc)
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
