"""POST /discover — widget self-discovery: pages index themselves on first visit."""
import json
from services.discovery import discover_page


def _r(status, data):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data)}


def handle_discover(body: dict) -> dict:
    """
    Index a page self-reported by the nav widget.

    Args:
        body: dict with keys:
            path        (str, required)  — absolute portal path
            label       (str, required)  — page title / h1
            description (str, optional)  — meta description or heading summary
            tags        (list, optional) — headings and action texts

    Returns:
        Lambda proxy response: {indexed: bool, reason: "new"|"updated"|"unchanged"}.
        ValueError from sanitisation bubbles to the handler's 400 mapping.
    """
    return _r(200, discover_page(body))
