# portal-nav-api

A self-contained portal navigation AI service. Answers "where is X on our portal?" without a commercial LLM call on every request.

Pluggable via REST — callable from any system that can make an HTTP request.

---

## How it works

Three-layer cascade, cheapest first:

```
Query → L0 (hot-path fuzzy match, ~1ms)
      → L1 (ONNX semantic embedding search, ~20–50ms)
      → L2 (ONNX cross-encoder re-rank, ~180ms)
      → MISS
```

- **L0** — up to 70 admin-configurable frequently-used paths, ranked by usage. Levenshtein fuzzy match against labels and aliases. No model needed.
- **L1** — `all-MiniLM-L6-v2` sentence embedding + pgvector cosine search against the indexed page catalogue.
- **L2** — `cross-encoder/ms-marco-MiniLM-L-6-v2` re-ranker over L1 candidates when L1 confidence is below threshold.

Both ONNX models are baked into the Lambda container at build time — no Bedrock or OpenAI call on the hot path.

---

## Live endpoint

```
https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
```

---

## API reference

All endpoints return `application/json`.

### `GET /health`
No auth. Always returns 200.
```json
{ "status": "ok", "version": "..." }
```

### `POST /query`
Auth: `x-api-key: <key>`
```json
{ "query": "submit a claim" }
```
Response:
```json
{
  "path":        "/claims/submit",
  "label":       "Submit a Claim",
  "confidence":  0.9124,
  "layer":       "L0",
  "response_ms": 3,
  "candidates":  [],
  "suggestion":  null
}
```
`layer` is one of `L0 | L1 | L2 | MISS`. On `MISS`, `path` is `null` and `confidence` is `0`.

### `POST /query/batch`
Auth: `x-api-key: <key>`
```json
{ "queries": ["submit a claim", "renew policy"] }
```
Returns an array of results in the same order as input. Maximum 20 queries per call.

### `GET /query/suggest?q=<prefix>`
No auth. Returns label-prefix matches from the index.
```json
[{ "path": "/claims/submit", "label": "Submit a Claim" }]
```

### Admin endpoints (Bearer token required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/hot-paths` | List hot-path registry |
| `POST` | `/admin/hot-paths` | Add / update a hot-path |
| `POST` | `/admin/hot-paths/evict` | Remove stale cold paths |
| `GET` | `/admin/index` | List indexed pages |
| `POST` | `/admin/index` | Index a page (generates embedding) |
| `POST` | `/admin/index/reindex-all` | Re-embed all indexed pages |
| `GET` | `/admin/stats` | Query counts and layer hit rates (24h) |
| `GET` | `/admin/config` | Read live threshold configuration |
| `PUT` | `/admin/config` | Update thresholds at runtime |

#### Index a page
```bash
curl -X POST https://.../admin/index \
  -H "Authorization: Bearer $NAV_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path":"/claims/submit","label":"Submit a Claim","description":"File insurance claims","tags":["claims"]}'
```

#### Register a hot-path
```bash
curl -X POST https://.../admin/hot-paths \
  -H "Authorization: Bearer $NAV_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path":"/claims/submit","label":"Submit a Claim","aliases":["file a claim","claims form"],"pinned":false}'
```

---

## Authentication

| Credential | Header | Used for |
|---|---|---|
| `NAV_API_KEY` | `x-api-key: <key>` | `/query`, `/query/batch` |
| `NAV_ADMIN_TOKEN` | `Authorization: Bearer <token>` | `/admin/*` |

Keys are validated with `hmac.compare_digest` — constant-time, timing-attack resistant.

---

## Running tests locally

### Wave 1/2 — Python invariants (no DB or ONNX required)

```bash
pip install -r requirements-dev.txt
python -m pytest tests/invariants/ -v
# 33 pass, ~41 skip (integration-pending[rds/onnx])
```

With RDS access (full suite):
```bash
DATABASE_URL="postgresql://..." \
API_KEYS="..." \
ADMIN_TOKEN="..." \
python -m pytest tests/invariants/ -v
```

### Wave 3 — Jest live-API tests

```bash
cd tests/wave3
npm install
NAV_API_KEY="..." NAV_ADMIN_TOKEN="..." npm test
# 43 pass
```

---

## Deployment

Every push to `master` triggers:

```
appsec (CodeQL + Semgrep + OWASP-DC + Gitleaks + Trivy)
test-unit → build (Docker → ECR) → deploy (Lambda) → test-integration-python
                                                    → test-integration-wave3
```

Manual redeploy:
```bash
git commit --allow-empty -m "chore: trigger redeploy" && git push origin master
```

---

## Infrastructure

| Resource | Value |
|---|---|
| Runtime | AWS Lambda (container image, 1024 MB, 60s timeout) |
| API | AWS API Gateway HTTP API v2 |
| Database | AWS RDS PostgreSQL 16 (`portal-nav-db`, `eu-west-1`) |
| Registry | AWS ECR (`portal-nav-api`) |
| Region | `eu-west-1` |

---

## Configuration (Lambda env vars)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `API_KEYS` | — | Comma-separated list of valid API keys |
| `ADMIN_TOKEN` | — | Admin bearer token |
| `HOT_PATH_THRESHOLD` | `0.75` | Min confidence for L0 hit |
| `L1_THRESHOLD` | `0.65` | Min confidence for L1 hit |
| `L2_THRESHOLD` | `0.50` | Min confidence for L2 hit |
| `MAX_HOT_PATHS` | `70` | Max rows loaded from hot-path registry |
| `LOG_LEVEL` | `INFO` | Python log level |

Thresholds can also be updated at runtime via `PUT /admin/config` without redeployment.

---

## Security

- AppSec pipeline: CodeQL + Semgrep (7 custom rules) + OWASP-DC + Gitleaks + Trivy + ZAP
- Runbook: [`docs/governance/appsec-runbook.md`](docs/governance/appsec-runbook.md)
- Findings: GitHub → Security → Code scanning alerts
