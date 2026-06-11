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
        _pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=url)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            conn.commit()
        _run_migrations()
        _load_config_overrides()
        logger.info("DB pool ready")
    except Exception as e:
        logger.error("DB pool init failed: %s", e)
        _pool = None


class get_conn:
    """Context manager — borrows a connection from pool, returns it on exit."""
    def __enter__(self):
        if _pool is None:
            raise RuntimeError("DB pool not initialised")
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
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Bound DDL time: if a previous migration is holding a lock
            # (e.g. a failed cold start), fail fast rather than blocking.
            cur.execute("SET lock_timeout = '3s'")
            cur.execute(ddl)
        conn.commit()
    logger.info("Migrations applied")


def _load_config_overrides():
    """Load operator-persisted config from nav_config into the settings singleton.

    Allows PUT /admin/config changes to survive Lambda cold starts — values
    written to nav_config take precedence over the env-var defaults in Settings.
    Only whitelisted numeric keys are applied; unknown keys are ignored.
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
        for key, value in rows:
            if key in _CAST:
                setattr(settings, key, _CAST[key](value))
                logger.info("config override: %s = %s", key, value)
    except Exception as exc:
        logger.warning("_load_config_overrides failed (non-fatal): %s", exc)
