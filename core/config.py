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


def _float_env(name: str, default: str, lo: float, hi: float) -> float:
    val = float(os.environ.get(name, default))
    if not (lo <= val <= hi):
        raise ValueError(f"{name}={val} out of range [{lo}, {hi}]")
    return val


def _int_env(name: str, default: str, lo: int, hi: int) -> int:
    val = int(os.environ.get(name, default))
    if not (lo <= val <= hi):
        raise ValueError(f"{name}={val} out of range [{lo}, {hi}]")
    return val


_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    API_KEYS: list = _KEYS
    KEY_SCOPES: dict = _KEY_SCOPES
    # Ranking multiplier for results from scope sites other than the key's
    # home site — shared content stays findable but home pages win ties.
    CROSS_SITE_PENALTY: float = _float_env("CROSS_SITE_PENALTY", "0.85", 0.0, 1.0)
    # Score multiplier applied to candidates sharing the user's current page segment.
    CONTEXT_BOOST_FACTOR: float = _float_env("CONTEXT_BOOST_FACTOR", "1.10", 0.01, 10.0)
    # Fixed confidence score assigned to all L3 keyword fallback results. Kept below
    # the auto-navigate threshold so the client always presents them as a pick-list.
    L3_CONFIDENCE: float = _float_env("L3_CONFIDENCE", "0.50", 0.0, 1.0)
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
    HOT_PATH_THRESHOLD: float = _float_env("HOT_PATH_THRESHOLD", "0.75", 0.0, 1.0)
    L1_THRESHOLD: float = _float_env("L1_THRESHOLD", "0.65", 0.0, 1.0)
    L2_THRESHOLD: float = _float_env("L2_THRESHOLD", "0.50", 0.0, 1.0)
    MAX_HOT_PATHS: int = _int_env("MAX_HOT_PATHS", "70", 1, 1000)
    SERVICE_VERSION: str = os.environ.get("SERVICE_VERSION", "1.0.0")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    # ── DB pool sizing ───────────────────────────────────────────────────────
    # Lambda functions share a pool within a single execution environment.
    # maxconn=5 is right for Lambda (each instance is single-threaded for
    # Lambda itself, but ThreadPoolExecutor in handle_batch can use up to 5
    # workers). Expose as env vars so load tests can tune without code changes.
    DB_POOL_MINCONN: int = _int_env("DB_POOL_MINCONN", "1", 1, 20)
    DB_POOL_MAXCONN: int = _int_env("DB_POOL_MAXCONN", "5", 1, 100)
    # ── Feedback / promotion tuning ──────────────────────────────────────────
    PROMOTE_UNIQUE_QUERIES: int = _int_env("PROMOTE_UNIQUE_QUERIES", "3", 1, 100)
    PROMOTE_WINDOW_DAYS: int = _int_env("PROMOTE_WINDOW_DAYS", "7", 1, 365)
    PROMOTE_MIN_CONFIDENCE: float = _float_env("PROMOTE_MIN_CONFIDENCE", "0.60", 0.0, 1.0)
    MAX_ALIASES: int = _int_env("MAX_ALIASES", "12", 1, 100)
    ALIAS_MAX_LEN: int = _int_env("ALIAS_MAX_LEN", "60", 1, 500)
    ALIAS_DUP_RATIO: float = _float_env("ALIAS_DUP_RATIO", "0.90", 0.0, 1.0)
    # ── Miss-mining tuning ───────────────────────────────────────────────────
    CLUSTER_SIMILARITY: float = _float_env("CLUSTER_SIMILARITY", "0.80", 0.0, 1.0)
    MIN_CLUSTER_COUNT: int = _int_env("MIN_CLUSTER_COUNT", "1", 1, 1000)
    # ── Per-tenant threshold overrides ───────────────────────────────────────
    # Populated at cold start by _load_config_overrides() from nav_config rows
    # with keys of the form "<site_id>:L1_THRESHOLD" etc.  Declared here so
    # attribute access never raises AttributeError before the DB is ready.
    SITE_OVERRIDES: dict = {}
    # Process-level alias cache: (site_id, lower(old_path)) → new_path.
    # Populated at cold start by db.load_alias_cache(); invalidated and
    # reloaded after any alias write via routes/admin.py.
    ALIAS_CACHE: dict = {}


settings = Settings()
