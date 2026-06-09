import json
from core.db import check_connection
from core.config import settings
from services.embedding import _session as emb_session


def handle_health():
    db_ok = check_connection()
    count = 0
    if db_ok:
        try:
            from services.hot_path import get_top_paths
            count = len(get_top_paths(limit=1))
        except Exception:
            pass
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "ok",
            "version": settings.SERVICE_VERSION,
            "db_connected": db_ok,
            "embedding_model_loaded": emb_session is not None,
            "hot_path_count": count,
        }),
    }
