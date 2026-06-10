"""
portal-nav-api — AWS Lambda entry point.
Routes: /query  /query/batch  /query/suggest  /health  /admin/*
"""
import json
import logging

# X-Ray tracing — patch all supported libraries (psycopg2, requests).
# Must run before any library import so the patches take effect.
# LAMBDA_TASK_ROOT is always set in the Lambda runtime; only patch there
# to avoid breaking local test runs where aws-xray-sdk may not be installed.
import os
if os.environ.get("LAMBDA_TASK_ROOT"):
    from aws_xray_sdk.core import xray_recorder, patch_all
    xray_recorder.configure(service="portal-nav-api")
    patch_all()

# Module-level init — runs once per cold start, reused on warm invocations
from core.config import settings

# Configure log level from settings after the import above.
# settings.LOG_LEVEL reads LOG_LEVEL from the environment via core.config.
logger = logging.getLogger()
logger.setLevel(settings.LOG_LEVEL)
from core.db import init_pool
from services.embedding import load_model
from services.reranker import load_reranker

load_model()
load_reranker()
init_pool()


def lambda_handler(event, context):
    path = event.get("rawPath", "/")
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    logger.info(json.dumps({"path": path, "method": method}))

    try:
        if path == "/health" and method == "GET":
            from routes.health import handle_health
            return handle_health()

        if path in ("/query", "/query/") and method == "POST":
            from core.auth import validate_api_key
            from routes.query import handle_query
            validate_api_key(headers)
            return handle_query(_body(event))

        if path in ("/query/batch", "/query/batch/") and method == "POST":
            from core.auth import validate_api_key
            from routes.query import handle_batch
            validate_api_key(headers)
            return handle_batch(_body(event))

        if path in ("/query/suggest", "/query/suggest/") and method == "GET":
            from routes.query import handle_suggest
            q = (event.get("queryStringParameters") or {}).get("q", "")
            return handle_suggest(q)

        # POST /navigate — feedback endpoint (no auth; called by widget after navigation)
        # Intentionally unauthenticated: the data written is non-sensitive navigation
        # telemetry.  Rate-limited at API Gateway (50 req/s) which is sufficient
        # protection against bulk poisoning of the promotion counter.
        if path in ("/navigate", "/navigate/") and method == "POST":
            from routes.navigate import handle_navigate
            return handle_navigate(_body(event))

        if path.startswith("/admin"):
            from core.auth import validate_admin_token
            from routes.admin import handle_admin
            validate_admin_token(headers)
            params = event.get("queryStringParameters") or {}
            body = _body(event) if method in ("POST", "PUT", "PATCH") else {}
            return handle_admin(path, method, body, params)

        return _r(404, {"error": "Not found", "path": path})

    except PermissionError as e:
        return _r(401, {"error": str(e)})
    except ValueError as e:
        return _r(400, {"error": str(e)})
    except Exception:
        logger.exception("Unhandled error")
        return _r(500, {"error": "Internal server error"})


def _body(event):
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode()
    try:
        return json.loads(body)
    except Exception:
        return {}


def _r(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data),
    }
