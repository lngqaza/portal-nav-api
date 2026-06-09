# portal-nav-api — Invariant Catalogue

Invariants are unconditional correctness properties.
Every one must hold for every input, in every environment, at every point in time.
A violation is a defect, not a configuration issue.

---

## I. Authentication & Authorisation

| ID | Invariant |
|----|-----------|
| AUTH-01 | `POST /query` with a missing or unknown `X-API-Key` header always returns HTTP 401 |
| AUTH-02 | `POST /query` with a valid `X-API-Key` never returns HTTP 401 |
| AUTH-03 | `/admin/*` with a missing or wrong `Authorization: Bearer` always returns HTTP 401 |
| AUTH-04 | API key validation is constant-time (immune to timing attacks via simple equality on list) |
| AUTH-05 | `GET /health` and `GET /query/suggest` require no authentication |

---

## II. Query Router Cascade

| ID | Invariant |
|----|-----------|
| ROUTE-01 | Every call to `route_query` returns exactly one `NavigationResult` — never raises |
| ROUTE-02 | `NavigationResult.layer` is always one of `{L0, L1, L2, MISS}` |
| ROUTE-03 | L1 is never called when L0 returns a result |
| ROUTE-04 | L2 is never called when L1 confidence ≥ L1_THRESHOLD |
| ROUTE-05 | L2 is never called when L1 returns zero candidates |
| ROUTE-06 | A MISS result always has `path=None`, `confidence=0.0` |
| ROUTE-07 | A non-MISS result always has `path` and `label` as non-empty strings |
| ROUTE-08 | `response_ms` is always a non-negative integer |
| ROUTE-09 | Every query is written to `nav_query_log` exactly once |

---

## III. L0 — Hot Path Registry

| ID | Invariant |
|----|-----------|
| L0-01 | `lookup` never returns a result with `confidence < HOT_PATH_THRESHOLD` |
| L0-02 | `lookup` returns `None` when the table is empty |
| L0-03 | On a hit, `hit_count` for that row is incremented by exactly 1 |
| L0-04 | Pinned paths always have a rank contribution of +10 000 |
| L0-05 | `evict_cold_paths` never deletes a row where `pinned = true` |
| L0-06 | `evict_cold_paths` never deletes a row with `hit_count >= min_hits_per_week` within the last 7 days |
| L0-07 | Fuzzy score is always in [0.0, 1.0] |
| L0-08 | Alias matching is case-insensitive |

---

## IV. L1 — Embedding Search

| ID | Invariant |
|----|-----------|
| L1-01 | `encode` returns a unit vector (L2-norm = 1.0 ± 1e-5) or `None` |
| L1-02 | `encode` always returns a 384-dimensional array or `None` |
| L1-03 | `search` returns an empty list — never raises — when the model is not loaded |
| L1-04 | `search` returns results in descending score order |
| L1-05 | Every score from `search` is in [−1.0, 1.0] |
| L1-06 | `token_type_ids` is never passed to the ONNX model (filtered at call site) |
| L1-07 | `index_page` stores an embedding that is later retrievable by `search` |
| L1-08 | Indexing the same path twice is idempotent — no duplicate rows in `nav_index` |

---

## V. L2 — Re-ranker

| ID | Invariant |
|----|-----------|
| L2-01 | `rerank` never returns a result with score < L2_THRESHOLD |
| L2-02 | `rerank` returns `None` (not raises) when given an empty candidate list |
| L2-03 | When the reranker model is absent, `rerank` falls back to returning the best L1 candidate or `None` |
| L2-04 | `rerank` always returns one of the items from `candidates` — never a new object |

---

## VI. Database Schema

| ID | Invariant |
|----|-----------|
| DB-01 | `nav_hot_paths.hit_count` is always ≥ 0 |
| DB-02 | `nav_index.path` is unique — no duplicate entries |
| DB-03 | `nav_index.embedding` is always `vector(384)` when non-NULL |
| DB-04 | `nav_query_log` is append-only: rows are never deleted by application code |
| DB-05 | `run_migrations()` is idempotent — safe to call on a populated database |
| DB-06 | All four tables exist after `init_pool()` completes |

---

## VII. API Contract

| ID | Invariant |
|----|-----------|
| API-01 | Every successful query response contains exactly: `path`, `label`, `confidence`, `layer`, `response_ms`, `candidates`, `suggestion` |
| API-02 | `POST /query/batch` with > 20 queries always returns HTTP 400 |
| API-03 | `POST /query/batch` returns results in the same order as input queries |
| API-04 | `GET /health` always returns HTTP 200 (even when DB is down) |
| API-05 | `confidence` in responses is always rounded to 4 decimal places |
| API-06 | `response_ms` in responses is always an integer ≥ 0 |

---

## VIII. Configuration

| ID | Invariant |
|----|-----------|
| CFG-01 | `HOT_PATH_THRESHOLD`, `L1_THRESHOLD`, `L2_THRESHOLD` are always in (0.0, 1.0] |
| CFG-02 | `MAX_HOT_PATHS` is always a positive integer |
| CFG-03 | `API_KEYS` list is never empty (service refuses to start if unset) |
| CFG-04 | Thresholds satisfy: `HOT_PATH_THRESHOLD ≥ L1_THRESHOLD ≥ L2_THRESHOLD` is not enforced, but each layer independently gates on its own threshold |
