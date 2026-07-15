# Phantom-table audit — portal-nav-api

**Date:** 2026-07-15
**Result: CLEAN** — no SQL references a table that is never created.

## Why this audit exists
A phantom-table cleanup in `sanlamconnect-lxp` (see that repo's
`docs/audit/phantom-tables.md`) found runtime 500s caused by SQL referencing tables
that were never created. This repo was swept for the same pattern.

## Method
Static created-vs-referenced diff over the Python source: every table named in
`FROM` / `JOIN` / `INSERT INTO` / `UPDATE` / `DELETE FROM` checked against every
`CREATE TABLE`/`VIEW`. Candidates verified by hand.

## Result
- All 8 tables the app queries (`nav_audit_log`, `nav_config`, `nav_hot_paths`,
  `nav_index`, `nav_navigate_log`, `nav_path_aliases`, `nav_query_log`, `nav_sites`)
  are created in `core/db.py`.
- The diff's apparent "extra references" were **not** SQL — they were Python
  `from … import` statements (which match the `FROM` pattern), stdlib/module names,
  and Postgres system catalogs (`pg_constraint`, `information_schema`).

## Caveat
Static, table-level pass only — it does not catch column-level mismatches or
runtime-only failures. CloudWatch `42P01`/`42703` monitoring is the ongoing net.
