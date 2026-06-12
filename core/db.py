"""
PostgreSQL connection pool (psycopg2).
Initialised once at Lambda cold start, reused across warm invocations.
Runs idempotent schema migrations on first connect.

SIGTERM handling: Lambda sends SIGTERM before SIGKILL when a function times out
or is being shut down.  We register a handler and an atexit hook so the
connection pool is closed cleanly rather than being abandoned, which would
leave dangling connections on RDS until the idle timeout (default 10 min).
"""
import atexit
import logging
import signal

import psycopg2
import psycopg2.pool

from core.config import settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _close_pool(signum=None, frame=None) -> None:
    """
    Close every connection in the pool.

    Called on SIGTERM and at process exit via atexit.  Idempotent — safe to
    call multiple times.  Swallows all exceptions so it never prevents an
    orderly shutdown.
    """
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
            logger.info("DB pool closed cleanly")
        except Exception as exc:  # pragma: no cover
            logger.warning("DB pool close error: %s", exc)
        finally:
            _pool = None


# Register once at import time.  Both hooks are idempotent.
signal.signal(signal.SIGTERM, _close_pool)
atexit.register(_close_pool)


def init_pool():
    global _pool
    if _pool is not None:
        return
    url = settings.DATABASE_URL
    for old, new in (("postgresql+asyncpg://", "postgresql://"), ("postgres+asyncpg://", "postgresql://")):
        if url.startswith(old):
            url = new + url[len(old):]
    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=settings.DB_POOL_MINCONN,
            maxconn=settings.DB_POOL_MAXCONN,
            dsn=url,
        )
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            conn.commit()
        _run_migrations()
        _load_config_overrides()
        settings.ALIAS_CACHE = load_alias_cache()
        logger.info("DB pool ready")
    except Exception as e:
        logger.error("DB pool init failed: %s", e)
        _pool = None


class get_conn:
    """Context manager — borrows a connection from pool, returns it on exit."""
    def __enter__(self):
        if _pool is None:
            raise RuntimeError("DB pool not initialised")
        # psycopg2 ThreadedConnectionPool.getconn() has no timeout parameter;
        # fast-fail under pool exhaustion is handled by the PoolError that
        # psycopg2 raises immediately when maxconn is reached.
        self._conn = _pool.getconn()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        _pool.putconn(self._conn)
        return False


def check_connection() -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def _run_migrations():
    """Idempotent schema — safe to run on every cold start."""
    ddl = """
    CREATE TABLE IF NOT EXISTS nav_hot_paths (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        path        VARCHAR(500) NOT NULL,
        label       VARCHAR(200) NOT NULL,
        aliases     TEXT[] DEFAULT '{}',
        hit_count   INTEGER NOT NULL DEFAULT 0,
        last_hit_at TIMESTAMP,
        pinned      BOOLEAN NOT NULL DEFAULT false,
        created_at  TIMESTAMP DEFAULT now(),
        updated_at  TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS nav_index (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        path        VARCHAR(500) UNIQUE NOT NULL,
        label       VARCHAR(200) NOT NULL,
        description VARCHAR(1000) DEFAULT '',
        tags        TEXT[] DEFAULT '{}',
        created_at  TIMESTAMP DEFAULT now()
    );

    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='nav_index' AND column_name='embedding'
        ) THEN
            ALTER TABLE nav_index ADD COLUMN embedding vector(384);
        END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS nav_query_log (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        raw_query    VARCHAR(500) NOT NULL,
        matched_path VARCHAR(500),
        layer_used   VARCHAR(10) NOT NULL,
        confidence   FLOAT DEFAULT 0.0,
        response_ms  INTEGER DEFAULT 0,
        created_at   TIMESTAMP DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS nav_config (
        key        VARCHAR(100) PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT now()
    );

    -- Navigation feedback log — records explicit user navigations from widget.
    -- Drives auto-promotion of popular L1/L2 results to L0 hot-paths.
    CREATE TABLE IF NOT EXISTS nav_navigate_log (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        raw_query       VARCHAR(500) NOT NULL,
        navigated_path  VARCHAR(500) NOT NULL,
        label           VARCHAR(200) NOT NULL DEFAULT '',
        confidence      FLOAT NOT NULL DEFAULT 0.0,
        created_at      TIMESTAMP DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_hot_paths_rank       ON nav_hot_paths(hit_count DESC);
    CREATE INDEX IF NOT EXISTS idx_query_log_created    ON nav_query_log(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_query_log_layer      ON nav_query_log(layer_used);
    CREATE INDEX IF NOT EXISTS idx_navigate_log_path    ON nav_navigate_log(navigated_path, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_navigate_log_created ON nav_navigate_log(created_at DESC);

    -- DB-01: hit_count must never go negative.
    -- Idempotent: only adds the constraint if it does not already exist.
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'chk_hit_count_non_negative'
              AND conrelid = 'nav_hot_paths'::regclass
        ) THEN
            ALTER TABLE nav_hot_paths
                ADD CONSTRAINT chk_hit_count_non_negative CHECK (hit_count >= 0);
        END IF;
    END $$;

    -- nav_hot_paths.path must be unique — upsert_path depends on one row per path.
    -- Idempotent: only adds the constraint if it does not already exist.
    -- (uq_hot_paths_path was superseded by uq_hot_paths_site_path below —
    -- the old single-column unique is dropped in the multi-tenancy block.)

    -- Self-discovery dedup: hash of last-indexed content per page so
    -- re-visits skip re-embedding unless the page changed.
    ALTER TABLE nav_index ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

    -- Multi-tenancy: every row belongs to a site (tenant), derived from the
    -- API key at request time. Pre-existing rows keep the 'default' site so
    -- the original portal needs no data migration. Uniqueness moves from
    -- (path) to (site_id, path) so different sites can share path names.
    ALTER TABLE nav_index        ADD COLUMN IF NOT EXISTS site_id VARCHAR(64) NOT NULL DEFAULT 'default';
    ALTER TABLE nav_hot_paths    ADD COLUMN IF NOT EXISTS site_id VARCHAR(64) NOT NULL DEFAULT 'default';
    ALTER TABLE nav_query_log    ADD COLUMN IF NOT EXISTS site_id VARCHAR(64) NOT NULL DEFAULT 'default';
    ALTER TABLE nav_navigate_log ADD COLUMN IF NOT EXISTS site_id VARCHAR(64) NOT NULL DEFAULT 'default';

    DO $$ BEGIN
        ALTER TABLE nav_index     DROP CONSTRAINT IF EXISTS nav_index_path_key;
        ALTER TABLE nav_hot_paths DROP CONSTRAINT IF EXISTS uq_hot_paths_path;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_nav_index_site_path'
        ) THEN
            ALTER TABLE nav_index ADD CONSTRAINT uq_nav_index_site_path UNIQUE (site_id, path);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_hot_paths_site_path'
        ) THEN
            ALTER TABLE nav_hot_paths ADD CONSTRAINT uq_hot_paths_site_path UNIQUE (site_id, path);
        END IF;
    END $$;

    -- nav_query_log.layer_used must be a valid cascade level.
    -- Recreated idempotently: L3 (keyword fallback) and L4 (weak candidates)
    -- were added to the cascade, so the original four-value constraint is
    -- dropped and replaced with the six-value form.
    DO $$ BEGIN
        ALTER TABLE nav_query_log DROP CONSTRAINT IF EXISTS chk_layer_used_valid;
        ALTER TABLE nav_query_log
            ADD CONSTRAINT chk_layer_used_valid
                CHECK (layer_used IN ('L0', 'L1', 'L2', 'L3', 'L4', 'MISS'));
    END $$;

    -- Landing-page inference: record which page the user was on when they queried.
    -- Drives context-boost analysis and future personalization.
    ALTER TABLE nav_query_log ADD COLUMN IF NOT EXISTS context_path VARCHAR(500);

    -- Lambda request ID: correlates a DB row with a specific CloudWatch Logs event.
    -- VARCHAR(64) covers the standard 36-char UUID format with room to spare.
    ALTER TABLE nav_query_log ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);

    -- Audit trail: who/what last modified a hot-path row.
    -- action_source: 'api'|'auto-promote'|'alias-learn'|'evict'
    ALTER TABLE nav_hot_paths ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100) DEFAULT 'system';
    ALTER TABLE nav_hot_paths ADD COLUMN IF NOT EXISTS action_source VARCHAR(50) DEFAULT 'api';

    -- Tenant registry — one row per site_id.  Provides a single authoritative
    -- list for validation and future FK constraints.  Idempotent: inserting
    -- 'default' again is a no-op thanks to ON CONFLICT DO NOTHING.
    CREATE TABLE IF NOT EXISTS nav_sites (
        site_id    VARCHAR(64) PRIMARY KEY,
        label      VARCHAR(200) NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT now()
    );
    INSERT INTO nav_sites (site_id, label) VALUES ('default', 'Default site')
        ON CONFLICT (site_id) DO NOTHING;

    -- Data retention: delete log rows older than 90 days.
    -- Runs on every cold start; cost is trivial if nothing is old enough to delete.
    -- For high-volume portals, partition nav_query_log by month instead.
    DELETE FROM nav_query_log    WHERE created_at < now() - interval '90 days';
    DELETE FROM nav_navigate_log WHERE created_at < now() - interval '90 days';

    -- Backfill: content_hash was added without DEFAULT so existing rows are NULL.
    -- Empty string is the sentinel for "not yet hashed" — the crawler skips
    -- rehashing pages whose hash matches the current content, so NULL rows
    -- would never be rehashed. Fill them once idempotently.
    UPDATE nav_index SET content_hash = '' WHERE content_hash IS NULL;

    -- HNSW index for approximate nearest-neighbour embedding search.
    -- ef_construction=64 / m=16: good recall/build-time tradeoff for this
    -- collection size (~10k pages). Required before pgvector 0.5 — CREATE
    -- INDEX IF NOT EXISTS is idempotent.
    CREATE INDEX IF NOT EXISTS idx_nav_index_embedding
        ON nav_index USING hnsw (embedding vector_cosine_ops)
        WITH (m=16, ef_construction=64);

    -- pg_trgm: trigram similarity for fast LIKE '%q%' suggest queries.
    -- Without this, every keystroke in the widget causes a sequential scan of
    -- nav_index. The GIN index lets PostgreSQL resolve leading-wildcard patterns
    -- in O(log N) instead of O(N). The extension is bundled with standard
    -- PostgreSQL distributions and is safe to create idempotently.
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX IF NOT EXISTS idx_nav_index_label_trgm
        ON nav_index USING GIN (lower(label) gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS idx_nav_index_desc_trgm
        ON nav_index USING GIN (lower(coalesce(description,'')) gin_trgm_ops);

    -- Audit log: immutable record of every admin write operation.
    -- FAIS PoI 12 requires a complete trail of changes to customer-facing navigation.
    CREATE TABLE IF NOT EXISTS nav_audit_log (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        site_id     VARCHAR(64) NOT NULL DEFAULT 'default',
        action      VARCHAR(20) NOT NULL,   -- POST | PUT | DELETE | PATCH
        resource    VARCHAR(200) NOT NULL,  -- e.g. /admin/hot-paths/<id>
        actor       VARCHAR(200) DEFAULT 'admin',
        payload     TEXT,                   -- JSON snapshot of request body (PII scrubbed)
        created_at  TIMESTAMP DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_audit_log_site_created ON nav_audit_log(site_id, created_at DESC);

    -- Path alias / redirect table: maps old or vanity paths to current paths.
    -- Query router checks this on MISS before returning no-match, allowing
    -- seamless navigation even after portal restructuring.
    CREATE TABLE IF NOT EXISTS nav_path_aliases (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        site_id     VARCHAR(64) NOT NULL DEFAULT 'default',
        old_path    VARCHAR(500) NOT NULL,
        new_path    VARCHAR(500) NOT NULL,
        created_at  TIMESTAMP DEFAULT now()
    );
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_path_aliases_site_old'
        ) THEN
            ALTER TABLE nav_path_aliases
                ADD CONSTRAINT uq_path_aliases_site_old UNIQUE (site_id, old_path);
        END IF;
    END $$;
    CREATE INDEX IF NOT EXISTS idx_path_aliases_lookup ON nav_path_aliases(site_id, old_path);

    -- Per-tenant retention: honour site-specific retention_days from nav_config.
    -- The DEFAULT 90-day sweep below is a safety net; the Python cold-start
    -- code applies per-site values loaded from nav_config after this DDL block runs.
    -- (Rows without a site-specific override are caught by the generic DELETE above.)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '3s'")
            cur.execute(ddl)
            # Per-tenant retention: each site may configure its own retention_days
            # in nav_config as "<site_id>:retention_days". Apply those deletes now.
            cur.execute(
                "SELECT key, value FROM nav_config WHERE key LIKE '%:retention_days'"
            )
            for key, value in cur.fetchall():
                try:
                    site = key.split(":retention_days")[0]
                    days = int(value)
                    cur.execute(
                        "DELETE FROM nav_query_log WHERE site_id=%s AND created_at < now() - (interval '1 day' * %s)",
                        (site, days),
                    )
                    cur.execute(
                        "DELETE FROM nav_navigate_log WHERE site_id=%s AND created_at < now() - (interval '1 day' * %s)",
                        (site, days),
                    )
                except Exception as exc:
                    logger.warning("per-tenant retention failed for %s: %s", key, exc)
        conn.commit()
    logger.info("Migrations applied")


def load_alias_cache() -> dict:
    """Build a process-level alias lookup cache from nav_path_aliases.

    Returns a dict keyed by (site_id, lower(old_path)) → new_path.
    Called at cold start and after any alias write so query_router can
    resolve aliases with a dict lookup instead of a DB round-trip on
    every MISS (~5ms saved per non-matching query under load).
    An empty dict is returned on DB failure — the cache is advisory;
    query_router falls through to a live DB lookup when the key is absent.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT site_id, old_path, new_path FROM nav_path_aliases")
                rows = cur.fetchall()
        cache = {(r[0], r[1].lower()): r[2] for r in rows}
        logger.info("alias cache loaded: %d entries", len(cache))
        return cache
    except Exception as exc:
        logger.warning("alias cache load failed (non-fatal): %s", exc)
        return {}


def _load_config_overrides():
    """Load operator-persisted config from nav_config into the settings singleton.

    Global keys (no site prefix): override the process-wide Settings defaults.
    Per-tenant keys (format "<site_id>:KEY"): stored in settings.SITE_OVERRIDES
    dict — query_router loads them at request time for per-site threshold routing.
    """
    _CAST = {
        "MAX_HOT_PATHS": int,
        "HOT_PATH_THRESHOLD": float,
        "L1_THRESHOLD": float,
        "L2_THRESHOLD": float,
    }
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM nav_config")
                rows = cur.fetchall()
        site_overrides: dict = {}
        for key, value in rows:
            if ":" in key:
                # Per-tenant key: "<site_id>:THRESHOLD_NAME"
                site, cfg_key = key.split(":", 1)
                if cfg_key in _CAST:
                    site_overrides.setdefault(site, {})[cfg_key] = _CAST[cfg_key](value)
                    logger.info("per-tenant config: %s/%s = %s", site, cfg_key, value)
            elif key in _CAST:
                setattr(settings, key, _CAST[key](value))
                logger.info("config override: %s = %s", key, value)
        # Attach per-tenant overrides to the settings singleton so route_query
        # can resolve them at request time without a DB round-trip.
        settings.SITE_OVERRIDES = site_overrides
    except Exception as exc:
        logger.warning("_load_config_overrides failed (non-fatal): %s", exc)
