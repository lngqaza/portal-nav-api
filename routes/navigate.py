"""POST /navigate — records a user navigation event and triggers auto-promotion."""
import json
from core.auth import resolve_scope
from services.feedback import record_navigation


def _r(status, data):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(data)}


def handle_navigate(body: dict) -> dict:
    """
    Record that a user explicitly navigated to a page from a query result.

    Called by the widget immediately after a successful navigation (fire-and-forget
    via navigator.sendBeacon or fetch keep-alive).  This closes the feedback loop:
    popular L1/L2 results graduate to L0 hot-paths automatically after
    PROMOTE_UNIQUE_QUERIES distinct queries within PROMOTE_WINDOW_DAYS.

    Args:
        body: dict with keys:
            query      (str, required)  — the raw query the user typed
            path       (str, required)  — the portal path navigated to
            label      (str, required)  — human-readable page label
            confidence (float, optional) — confidence score from the API (default 0)

    Returns:
        Lambda proxy response with recorded/promoted flags.
    """
    query      = str(body.get("query",      "")).strip()
    path       = str(body.get("path",       "")).strip()
    label      = str(body.get("label",      "")).strip()
    confidence = float(body.get("confidence", 0.0))

    if not query or not path or not label:
        return _r(400, {"error": "query, path, and label are required"})

    # sendBeacon cannot set headers, so the widget carries its API key in the
    # body; an unknown/absent key falls back to the default tenant.
    scope = resolve_scope(str(body.get("key", ""))) or ["default"]
    result = record_navigation(query, path, label, confidence, scope[0])
    return _r(200, result)
