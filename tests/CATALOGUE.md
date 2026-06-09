# portal-nav-api — Test Catalogue

Invariants are unconditional correctness properties.
Every one must hold for every input, in every environment, at every point in time.
A violation is a defect, not a configuration issue.

---

## Wave 1 & 2 — Python Invariants (`tests/invariants/`)

Run: `python -m pytest tests/invariants/ -v`
33 pass without DB/ONNX. 41 skip with explicit `integration-pending[rds/onnx]` reasons.

### I. Authentication & Authorisation (`test_auth.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| AUTH-01 | `POST /query` with missing/unknown `X-Api-Key` always returns 401 (×3) | ✅ unit |
| AUTH-02 | `POST /query` with valid key never returns 401 | ✅ unit |
| AUTH-03 | `/admin/*` with missing/wrong Bearer always returns 401 (×5) | ✅ unit |
| AUTH-04 | Credential validation uses `hmac.compare_digest` — constant-time (×3) | ✅ unit |
| AUTH-05 | `GET /health` and `GET /query/suggest` require no authentication (×2) | ✅ unit |

### II. Query Router Cascade (`test_query_router.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| ROUTE-01 | `route_query` never raises — always returns `NavigationResult` (×3) | ⏳ rds |
| ROUTE-02 | `layer` is always one of `{L0, L1, L2, MISS}` (×4) | ⏳ rds |
| ROUTE-03 | L1 never called when L0 returns a result | ✅ unit |
| ROUTE-04 | L2 never called when L1 confidence ≥ L1_THRESHOLD | ✅ unit |
| ROUTE-05 | L2 never called when L1 returns zero candidates | ✅ unit |
| ROUTE-06 | MISS result always has `path=None`, `confidence=0.0` | ✅ unit |
| ROUTE-07 | Non-MISS result always has non-empty `path` and `label` | ✅ unit |
| ROUTE-08 | `response_ms` is always a non-negative integer | ⏳ rds |
| ROUTE-09 | Every query written to `nav_query_log` exactly once | ⏳ rds |

### III. L0 — Hot Path Registry (`test_l0_hot_path.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| L0-01 | `lookup` never returns confidence < HOT_PATH_THRESHOLD (×2) | ⏳ rds |
| L0-02 | `lookup` returns `None` when table is empty | ⏳ rds |
| L0-03 | Hit count incremented by exactly 1 on match | ⏳ rds |
| L0-04 | Pinned paths always have rank contribution +10 000 | ⏳ rds |
| L0-05 | `evict_cold_paths` never deletes a pinned row | ⏳ rds |
| L0-06 | `evict_cold_paths` preserves active high-hit paths | ⏳ rds |
| L0-07 | Fuzzy score is always in [0.0, 1.0] | ⏳ rds |
| L0-08 | Alias matching is case-insensitive | ⏳ rds |

### IV. L1 — Embedding Search (`test_l1_embedding.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| L1-01 | `encode` returns unit vector (L2-norm = 1.0 ± 1e-5) or `None` (×2) | ⏳ onnx |
| L1-02 | `encode` returns 384-dimensional array or `None` | ⏳ onnx |
| L1-03 | `search` returns `[]` — never raises — when model not loaded | ✅ unit |
| L1-04 | `search` results are in descending score order | ⏳ onnx+rds |
| L1-05 | Every score from `search` is in [−1.0, 1.0] | ⏳ onnx+rds |
| L1-06 | `token_type_ids` never passed to ONNX model | ⏳ onnx |
| L1-07 | `index_page` stores embedding retrievable by `search` | ⏳ onnx+rds |
| L1-08 | Indexing same path twice is idempotent | ⏳ onnx+rds |

### V. L2 — Re-ranker (`test_l2_reranker.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| L2-01 | `rerank` never returns score < L2_THRESHOLD (×2) | ✅ unit + ⏳ onnx |
| L2-02 | `rerank` returns `None` on empty candidates list | ✅ unit |
| L2-03 | When model absent, `rerank` falls back gracefully | ✅ unit |
| L2-04 | `rerank` always returns one of the input candidates | ⏳ onnx |

### VI. Database Schema (`test_db_schema.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| DB-01 | `hit_count >= 0` enforced by CHECK constraint (×2) | ⏳ rds |
| DB-02 | `nav_index.path` is unique | ⏳ rds |
| DB-03 | `nav_index.embedding` is always `vector(384)` when non-NULL | ⏳ rds |
| DB-04 | `nav_query_log` is append-only — no app-level DELETE | ⏳ rds |
| DB-05 | `run_migrations()` is idempotent | ⏳ rds |
| DB-06 | All four tables exist after `init_pool()` completes | ⏳ rds |

### VII. API Contract (`test_api_contract.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| API-01 | Every successful response contains all 7 required fields (×2) | ⏳ rds |
| API-02 | `POST /query/batch` with > 20 queries returns 400 | ✅ unit |
| API-02b | `POST /query/batch` with exactly 20 queries returns 200 | ⏳ rds |
| API-03 | Batch results returned in same order as input | ⏳ onnx+rds |
| API-04 | `GET /health` always returns 200 (×2) | ✅ unit |
| API-05 | `confidence` rounded to 4 decimal places | ⏳ onnx+rds |
| API-06 | `response_ms` is non-negative integer | ⏳ rds |

### VIII. Configuration (`test_config.py`)

| ID | Invariant | Status |
|----|-----------|--------|
| CFG-01 | All thresholds in (0.0, 1.0] | ✅ unit |
| CFG-02 | `MAX_HOT_PATHS` is a positive integer | ✅ unit |
| CFG-03 | `API_KEYS` list is non-empty when service configured | ✅ unit |
| CFG-04 | `settings_override` restores original values on exit | ✅ unit |

---

## Wave 3 — HTTP-level Tests (`tests/wave3/`)

Run: `cd tests/wave3 && NAV_API_KEY=... NAV_ADMIN_TOKEN=... npm test`
All 43 tests pass against the live API. Suites skip with `integration-pending[live-api]` when credentials absent.

### Contract — API Shape (`contract/api-shape.test.js`) — 15 tests

| ID | Invariant |
|----|-----------|
| SHAPE-01 | `GET /health` → 200 `{ status: "ok" }` (no auth) |
| SHAPE-02 | `POST /query` response has all 7 required fields |
| SHAPE-03 | `confidence` is a number in [0, 1] |
| SHAPE-04 | `layer` is one of L0 \| L1 \| L2 \| MISS |
| SHAPE-05 | `response_ms` is a non-negative integer |
| SHAPE-06 | `candidates` is an array |
| SHAPE-07 | `suggestion` is null or a string |
| SHAPE-08 | `POST /query/batch` returns array; each item has all 7 fields |
| SHAPE-09 | `GET /query/suggest` returns array of `{ path, label }` |
| SHAPE-10 | `GET /admin/config` returns all threshold fields |
| SHAPE-11 | `GET /admin/stats` returns `total_queries_24h`, `layers`, `top_misses` |
| SHAPE-12 | `POST /query` without key → 401 |
| SHAPE-13 | `GET /admin/stats` without token → 401 |
| SHAPE-14 | `POST /query` with empty string → 400 |
| SHAPE-15 | `POST /query/batch` with 21 queries → 400 |

### Security — Adversarial Inputs (`security/input-abuse.test.js`) — 18 tests

| ID | Invariant |
|----|-----------|
| SEC-01 | SQL injection payloads → never 5xx (×3 payloads) |
| SEC-02 | XSS payloads not reflected unescaped (×3 payloads) |
| SEC-03 | 100 KB query body → 200/400/413, never 5xx |
| SEC-04 | Null bytes → never 5xx (×3 payloads) |
| SEC-05 | Unicode abuse (RTL, zero-width, homoglyphs) → never 5xx (×3 payloads) |
| SEC-06 | Batch mixed malicious + benign → 200, exactly 4 results |
| SEC-07 | Missing Content-Type → never 5xx |
| SEC-08 | Malformed JSON → 400 or 401, never 5xx |
| SEC-09 | 50-level nested JSON → never 5xx |
| SEC-10 | CRLF injection in header → 401/400 or client TypeError |
| SEC-11 | POST to GET-only `/query/suggest` → 404, never 5xx |
| SEC-12 | Path traversal `/../etc/passwd` → 404, never 5xx |

### Business — End-to-End Journeys (`business/end-to-end.test.js`) — 8 tests

| ID | Invariant |
|----|-----------|
| E2E-01 | Basic query returns well-formed NavigationResult |
| E2E-02 | Index a page → query returns valid result (any layer) |
| E2E-03 | Register hot-path → exact label returns L0 hit ≥ 0.75 confidence |
| E2E-04 | Unknown query → `layer=MISS`, `path=null`, `confidence=0` |
| E2E-05 | Batch preserves positional order; unknown query always MISS |
| E2E-06 | Suggest returns `{ path, label }` for known label prefix |
| E2E-07 | `PUT /admin/config` persists threshold; restored in afterAll |
| E2E-08 | Admin stats shape stable before and after query activity |

---

## Summary

| Wave | Suite | Tests | ✅ Pass | ⏳ Skip | ❌ Fail |
|------|-------|-------|--------|--------|--------|
| 1/2 | pytest invariants | 74 | 33 | 41 | 0 |
| 3 | Jest live-API | 43 | 43 | 0 | 0 |
| **Total** | | **117** | **76** | **41** | **0** |

**Skip key:**
- `⏳ rds` — requires RDS (VPC-restricted); runs in CI post-deploy job
- `⏳ onnx` — requires ONNX models (Lambda container only); runs in CI
- `⏳ onnx+rds` — requires both
- `⏳ live-api` — requires `NAV_API_KEY` + `NAV_ADMIN_TOKEN`; runs in CI Wave 3 job

**CI pipeline:**
```
push → appsec (parallel)
     → test-unit (33 pass) → build → deploy → test-integration-python (74 tests)
                                             → test-integration-wave3  (43 tests)
```
