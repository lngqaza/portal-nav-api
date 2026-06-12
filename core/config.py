"""Runtime configuration from environment variables. No pydantic — pure stdlib."""
import os


def _parse_keys(raw: str):
    """Parse API_KEYS entries: "key", "key:site", or "key:siteA|siteB|siteC".

    The first site is the key's HOME tenant — discovery, learning, and logs
    write there. The full list is the key's READ SCOPE — queries search all
    of it, with home-site results ranked above the rest. Bare keys map to
    the "default" tenant for backwards compat.

    Returns (keys, key_scopes): raw key list for auth, and key → [sites].
    """
    keys, key_scopes = [], {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        key, _, sites = entry.partition(":")
        keys.append(key)
        scope = [s.strip() for s in sites.split("|") if s.strip()] or ["default"]
        key_scopes[key] = scope
    return keys, key_scopes


_KEYS, _KEY_SCOPES = _parse_keys(os.environ.get("API_KEYS", ""))


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    API_KEYS: list = _KEYS
    KEY_SCOPES: dict = _KEY_SCOPES
    # Ranking multiplier for results from scope sites other than the key's
    # home site — shared content stays findable but home pages win ties.
    CROSS_SITE_PENALTY: float = float(os.environ.get("CROSS_SITE_PENALTY", "0.85"))
    # Score multiplier applied to candidates sharing the user's current page segment.
    CONTEXT_BOOST_FACTOR: float = float(os.environ.get("CONTEXT_BOOST_FACTOR", "1.10"))
    # Fixed confidence score assigned to all L3 keyword fallback results. Kept below
    # the auto-navigate threshold so the client always presents them as a pick-list.
    L3_CONFIDENCE: float = float(os.environ.get("L3_CONFIDENCE", "0.50"))
    # Set to "true" to enable L4 weak-candidate fallback (off by default — surfacing
    # low-confidence results can lower perceived quality in production portals).
    L4_ENABLED: bool = os.environ.get("L4_ENABLED", "false").lower() == "true"
    ADMIN_TOKEN: str = os.environ.get("ADMIN_TOKEN", "")
    EMBEDDING_MODEL_PATH: str = os.environ.get(
        "EMBEDDING_MODEL_PATH", "/var/task/onnx_models/minilm/model.onnx"
    )
    RERANKER_MODEL_PATH: str = os.environ.get(
        "RERANKER_MODEL_PATH", "/var/task/onnx_models/reranker/model.onnx"
    )
    HOT_PATH_THRESHOLD: float = float(os.environ.get("HOT_PATH_THRESHOLD", "0.75"))
    L1_THRESHOLD: float = float(os.environ.get("L1_THRESHOLD", "0.65"))
    L2_THRESHOLD: float = float(os.environ.get("L2_THRESHOLD", "0.50"))
    MAX_HOT_PATHS: int = int(os.environ.get("MAX_HOT_PATHS", "70"))
    SERVICE_VERSION: str = os.environ.get("SERVICE_VERSION", "1.0.0")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    # ── Feedback / promotion tuning ──────────────────────────────────────────
    PROMOTE_UNIQUE_QUERIES: int = int(os.environ.get("PROMOTE_UNIQUE_QUERIES", "3"))
    PROMOTE_WINDOW_DAYS: int = int(os.environ.get("PROMOTE_WINDOW_DAYS", "7"))
    PROMOTE_MIN_CONFIDENCE: float = float(os.environ.get("PROMOTE_MIN_CONFIDENCE", "0.60"))
    MAX_ALIASES: int = int(os.environ.get("MAX_ALIASES", "12"))
    ALIAS_MAX_LEN: int = int(os.environ.get("ALIAS_MAX_LEN", "60"))
    ALIAS_DUP_RATIO: float = float(os.environ.get("ALIAS_DUP_RATIO", "0.90"))
    # ── Miss-mining tuning ───────────────────────────────────────────────────
    CLUSTER_SIMILARITY: float = float(os.environ.get("CLUSTER_SIMILARITY", "0.80"))
    MIN_CLUSTER_COUNT: int = int(os.environ.get("MIN_CLUSTER_COUNT", "1"))
    # ── Per-tenant threshold overrides ───────────────────────────────────────
    # Populated at cold start by _load_config_overrides() from nav_config rows
    # with keys of the form "<site_id>:L1_THRESHOLD" etc.  Declared here so
    # attribute access never raises AttributeError before the DB is ready.
    SITE_OVERRIDES: dict = {}


settings = Settings()
