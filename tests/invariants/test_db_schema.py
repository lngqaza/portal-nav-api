"""
DB schema invariants — DB-01 through DB-06.
"""
import pytest


# ── DB-01: hit_count is always >= 0 ──────────────────────────────────────────

def test_db01_hit_count_non_negative_constraint(clean_db):
    """Database rejects negative hit_count values."""
    import psycopg2
    with pytest.raises((psycopg2.errors.CheckViolation, psycopg2.errors.NotNullViolation, Exception)):
        with clean_db.cursor() as cur:
            cur.execute(
                "INSERT INTO nav_hot_paths (path, label, hit_count) VALUES (%s, %s, %s)",
                ("/neg", "Negative", -1),
            )
        clean_db.commit()
    clean_db.rollback()


def test_db01_hit_count_starts_at_zero(clean_db):
    """hit_count defaults to 0 on insert."""
    with clean_db.cursor() as cur:
        cur.execute(
            "INSERT INTO nav_hot_paths (path, label) VALUES (%s, %s) RETURNING hit_count",
            ("/new-path", "New Path"),
        )
        hit_count = cur.fetchone()[0]
    assert hit_count == 0


# ── DB-02: nav_index.path is unique ──────────────────────────────────────────

def test_db02_nav_index_path_unique(clean_db):
    """Inserting the same path twice raises a unique constraint error."""
    import psycopg2
    with clean_db.cursor() as cur:
        cur.execute(
            "INSERT INTO nav_index (path, label) VALUES (%s, %s)",
            ("/dup", "Dup One"),
        )
    clean_db.commit()

    with pytest.raises(psycopg2.errors.UniqueViolation):
        with clean_db.cursor() as cur:
            cur.execute(
                "INSERT INTO nav_index (path, label) VALUES (%s, %s)",
                ("/dup", "Dup Two"),
            )
        clean_db.commit()
    clean_db.rollback()


# ── DB-03: embedding is vector(384) ──────────────────────────────────────────

def test_db03_embedding_wrong_dimension_rejected(clean_db):
    """Inserting a vector with wrong dimension is rejected by pgvector."""
    import psycopg2
    with pytest.raises(Exception):  # pgvector raises on dimension mismatch
        with clean_db.cursor() as cur:
            cur.execute(
                "INSERT INTO nav_index (path, label, embedding) VALUES (%s, %s, %s::vector)",
                ("/bad-dim", "Bad", "[1.0, 2.0, 3.0]"),  # 3-dim, not 384
            )
        clean_db.commit()
    clean_db.rollback()


# ── DB-04: nav_query_log has no DELETE in application code ───────────────────

def test_db04_query_log_not_deleted_by_app(clean_db):
    """Verify application code never issues DELETE against nav_query_log."""
    import ast, os, glob

    root = os.path.join(os.path.dirname(__file__), "..", "..")
    py_files = glob.glob(os.path.join(root, "**/*.py"), recursive=True)
    py_files = [f for f in py_files if "tests" not in f and ".git" not in f]

    violations = []
    for path in py_files:
        with open(path) as f:
            source = f.read()
        if "nav_query_log" in source and "DELETE" in source.upper():
            # Check it's not a comment or docstring — crude but effective
            for line in source.splitlines():
                stripped = line.strip()
                if "nav_query_log" in stripped and "DELETE" in stripped.upper() and not stripped.startswith("#"):
                    violations.append(f"{path}: {stripped}")

    assert not violations, f"Application code deletes from nav_query_log:\n" + "\n".join(violations)


# ── DB-05: migrations are idempotent ─────────────────────────────────────────

def test_db05_migrations_idempotent(clean_db):
    """run_migrations() can be called multiple times without error or data loss."""
    from core.db import _run_migrations

    # Seed some data
    with clean_db.cursor() as cur:
        cur.execute(
            "INSERT INTO nav_hot_paths (path, label) VALUES (%s, %s)",
            ("/persist", "Persist Me"),
        )
    clean_db.commit()

    # Run migrations again — should not raise or delete data
    _run_migrations()

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_hot_paths WHERE path='/persist'")
        count = cur.fetchone()[0]
    assert count == 1, "Idempotent migration deleted existing data"


# ── DB-06: all four tables exist after init ───────────────────────────────────

def test_db06_all_tables_exist(clean_db):
    """All four nav_ tables exist after migrations."""
    expected = {"nav_hot_paths", "nav_index", "nav_query_log", "nav_config"}
    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'nav_%'"
        )
        found = {row[0] for row in cur.fetchall()}
    missing = expected - found
    assert not missing, f"Missing tables: {missing}"
