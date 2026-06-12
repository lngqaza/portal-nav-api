# portal-nav-api — On-Call Runbook

**Service:** portal-nav-api (AWS Lambda + API Gateway, eu-west-1)  
**Repo:** https://github.com/lngqaza/portal-nav-api  
**On-call contact:** lngqaza@gmail.com  

---

## 1. Service Architecture

```
API Gateway → Lambda (portal-nav-api) → RDS PostgreSQL 16 + pgvector (eu-west-1)
                      │
                      ├─ L0  hot-path registry (psycopg2 pool, ~1ms)
                      ├─ L1  ONNX embedding search (MiniLM, ~8-50ms)
                      ├─ L2  ONNX cross-encoder reranker (~180ms)
                      ├─ L3  keyword fallback (SQL LIKE, ~5ms)
                      ├─ L4  weak candidates (disabled by default)
                      └─ MISS → CloudWatch EMF metric emitted
```

**Key env vars (Lambda function configuration):**

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | RDS connection string (from Secrets Manager at deploy time) |
| `API_KEYS` | Comma-sep list; format `key:site` or `key:siteA\|siteB` |
| `ADMIN_TOKEN` | Bearer token for `/admin/*` endpoints |
| `CORS_ORIGINS` | Comma-sep allowed origins — **must not be `*` in Lambda** |
| `HOT_PATH_THRESHOLD` | L0 similarity threshold (default 0.75) |
| `L1_THRESHOLD` | Embedding similarity gate (default 0.65) |
| `L2_THRESHOLD` | Reranker score gate (default 0.50) |
| `DB_POOL_MAXCONN` | psycopg2 max connections per Lambda instance (default 5) |

---

## 2. CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| `portal-nav-MISS-rate-high` | `Miss` metric > 20% over 5min | Check index coverage → run `/admin/miss-report` |
| `portal-nav-errors-5xx` | Lambda error count > 5 in 1min | Check CloudWatch Logs for traceback |
| `portal-nav-p99-latency` | p99 > 2000ms over 5min | Check ONNX cold-start; consider provisioned concurrency |
| `portal-nav-db-pool-timeout` | `DB pool timeout` log pattern | Reduce `DB_POOL_MAXCONN` or scale RDS instance |
| `portal-nav-cold-start` | Init duration > 5s | ONNX model load slow; check Lambda `/tmp` and layer size |

**Log Insights query — last 50 MISSes:**
```sql
fields @timestamp, site, request_id
| filter Miss = 1
| sort @timestamp desc
| limit 50
```

**Log Insights query — slow queries (p95 > 500ms):**
```sql
fields @timestamp, response_ms, layer_used, site
| filter response_ms > 500
| sort @timestamp desc
| limit 50
```

---

## 3. MISS Rate Spike

**Symptom:** CloudWatch `Miss` metric spikes above 20%.

**Diagnosis steps:**
```bash
# 1. Get top misses
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://<api-gw-id>.execute-api.eu-west-1.amazonaws.com/admin/miss-report?days=1"

# 2. Check index coverage
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://<api-gw-id>.execute-api.eu-west-1.amazonaws.com/admin/stats"
```

**Resolution options:**

| Cause | Fix |
|-------|-----|
| New content not indexed | POST to `/admin/index/crawl` with updated sitemap |
| L1 threshold too high | `PUT /admin/config {"L1_THRESHOLD": 0.60}` |
| Hot-path eviction too aggressive | `PUT /admin/config {"MAX_HOT_PATHS": 100}` |
| Query intent mismatch | Add alias: `POST /admin/aliases {"old_path": "...", "new_path": "..."}` |
| Index empty (cold environment) | Run bulk index: `POST /admin/index/bulk {"pages": [...]}` |

---

## 4. Lambda 5xx Errors

**Check Lambda logs:**
```bash
aws logs tail /aws/lambda/portal-nav-api --follow --region eu-west-1
```

**Common causes:**

| Error pattern | Cause | Fix |
|---------------|-------|-----|
| `DB pool not initialised` | Cold start DB init failed | Check `DATABASE_URL` secret; verify RDS SG allows Lambda SG |
| `DB pool timeout` | All 5 connections in use | Reduce Lambda concurrency limit OR increase `DB_POOL_MAXCONN` |
| `RuntimeError: CORS_ORIGINS` | Missing CORS env var in Lambda | Set `CORS_ORIGINS` in Lambda environment variables |
| `onnxruntime` import error | ONNX layer not attached | Verify Lambda layer `portal-nav-onnx-models` is attached |
| `psycopg2` import error | Binary layer missing | Verify `portal-nav-psycopg2` Lambda layer is attached |

---

## 5. High Latency

**Symptom:** p99 > 2s.

**Diagnosis:**
- **L2 path (reranker)** is the most expensive: ~180ms per call. If most queries hit L2, lower `L1_THRESHOLD` to promote more to L1.
- **Cold start**: ONNX model load takes 2–4s. Consider provisioned concurrency for latency-sensitive portals.
- **DB latency**: Check RDS CloudWatch `ReadLatency` metric. If elevated, check connection count and query plan.

```bash
# Check L2 usage rate
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  ".../admin/stats" | jq '.layers.L2'
```

---

## 6. Routine Operations

### Evict stale hot-paths (weekly)
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"min_hits_per_week": 50}' \
  ".../admin/hot-paths/evict"
```

### Re-index after content changes
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sitemap_url": "https://portal.sanlamconnect.co.za/sitemap.xml"}' \
  ".../admin/index/crawl"
```

### Adjust per-tenant threshold (e.g. lumo)
```bash
curl -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"site": "lumo", "L1_THRESHOLD": 0.70}' \
  ".../admin/config"
```

### Check audit trail
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  ".../admin/audit-log?site=lumo&limit=20" | jq .
```

### Run load test (k6 required)
```bash
k6 run \
  -e NAV_API_URL=https://<api-gw-id>.execute-api.eu-west-1.amazonaws.com \
  -e NAV_API_KEY=nav-... \
  -e NAV_ADMIN_TOKEN=... \
  tests/load/k6-load-test.js
```

---

## 7. Deployment

All deploys go via `git push origin master` → GitHub Actions → ECR → Lambda.

```bash
# Trigger deploy
SKIP_APPSEC_CHECK=1 git push origin master

# Monitor deploy
gh run list --repo lngqaza/portal-nav-api --limit 5
gh run watch --repo lngqaza/portal-nav-api

# Roll back to previous image (get digest from ECR)
aws lambda update-function-code \
  --function-name portal-nav-api \
  --image-uri 684756697968.dkr.ecr.eu-west-1.amazonaws.com/portal-nav-api:<previous-tag> \
  --region eu-west-1
```

---

## 8. POPIA / FAIS Compliance Notes

- **PII scrubbing**: SA IDs, emails, phone, card, CVV, account/policy numbers are stripped from `raw_query` before DB write (`_scrub()` in `services/query_router.py`).
- **Audit trail**: all admin write operations (POST/PUT/DELETE) write to `nav_audit_log`. Retention: 90 days default (configurable per tenant via `nav_config`).
- **Data retention**: `nav_query_log` and `nav_navigate_log` auto-purged at Lambda cold start after 90 days (POPIA Article 14).
- **FAIS PoI 12**: audit log provides complete trail of changes to customer-facing navigation. Query: `GET /admin/audit-log`.

---

## 9. Escalation

| Severity | Condition | Action |
|----------|-----------|--------|
| P1 | All queries returning 5xx | Page on-call; check Lambda logs; consider rolling back |
| P2 | MISS rate > 40% sustained | Trigger re-index; lower thresholds |
| P3 | p99 > 2s | Monitor; consider provisioned concurrency |
| P4 | MISS rate 20–40% | Investigate miss-report; add missing content |
