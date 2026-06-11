# HANDOVER — portal-nav-api: multi-tenancy rollout (resume point)

**Session name suggestion:** `portal-nav: finish multi-tenancy deploy + verify`
**Date:** 2026-06-11 · Repo: `lngqaza/portal-nav-api` (branch `master`) · Local: `C:\Users\e1000836\Desktop\portal-nav-api`
**Efficiency rules:** hyper token economy — batch calls, poll deploys with single curl, no re-reads, terse output. Full-auto: user runs bypass-permissions mode.

## ⚠️ IMMEDIATE NEXT STEP (deploy FAILED — diagnose first)
Latest `deploy-nav-api.yml` run on commit `bba90b3` ("Multi-tenancy: per-site index...") **completed failure**. Not yet diagnosed.
```bash
TOKEN=$(cd C:/Users/e1000836/Desktop/portal-nav-api && git remote get-url origin | sed 's/.*lngqaza:\(.*\)@github.*/\1/')
# list failed step:
RUN=$(curl -s -H "Authorization: token $TOKEN" "https://api.github.com/repos/lngqaza/portal-nav-api/actions/workflows/deploy-nav-api.yml/runs?per_page=1" | python -c "import json,sys; print(json.load(sys.stdin)['workflow_runs'][0]['id'])")
curl -s -H "Authorization: token $TOKEN" ".../actions/runs/$RUN/jobs"   # then job logs for failed step
```
Suspects: HuggingFace 429 during docker build (known flake — just re-run the workflow via API `POST /actions/runs/$RUN/rerun`), or the test step (unlikely — 46 pass locally).

## After deploy succeeds — remaining rollout steps (in order)
1. **Verify migration applied** (runs at Lambda startup): hit `/health`, then any `/query` — site_id columns + `(site_id,path)` uniques created idempotently by `core/db.py`.
2. **Clean stale Lumo rows from 'default' site** (they pre-date tenancy): via admin API
   `GET /admin/index?limit=200` (Bearer ADMIN_TOKEN from Lambda env `aws lambda get-function-configuration --function-name portal-nav-api --region eu-west-1`), delete ids for paths `/home.html /flights.html /hotels.html /bookings.html /contact-us.html` with `DELETE /admin/index/{id}`. Also check `nav_hot_paths` for `/claims-new.html` alias rows etc. — leave NovaSure ones.
3. **Re-crawl Lumo under its own site**: open `https://d6kupsfl5u4c6.cloudfront.net/home.html` once in Chrome (Claude-in-Chrome MCP; tab may exist). Widget auto-crawls all 5 pages → site `lumo`. (Use fresh tab/incognito-like: sessionStorage dedupe may suppress re-discovery — bump by clearing sessionStorage via JS or use new tab.)
4. **Verify isolation + boost** (single batch):
   - Lumo key `nav-d240be1101a43aa295f1dc26fe77e7e7`: "talk to a travel agent" must return a LUMO page (contact-us), **not** NovaSure `/support.html`.
   - NovaSure key `nav-9eadef81559f12263d150308a53b2975`: "where to log claims" still → `/claims-new.html` L0 (learned aliases live on site 'default', untouched).
   - Lumo voice/typo: "canccel my trip" → `/bookings.html`.
5. **Update demo-site/ACTIVATION_GUIDE.md**: replace shared-index limitation note with scope syntax (`key:siteA|siteB`, home site first, CROSS_SITE_PENALTY=0.85) — then `aws s3 sync demo-site s3://lumo-travel-demo-684756697968` + invalidate `E1KJRIM4W6FY0A`. Commit.

## What multi-tenancy IS (already built & committed, all tests green 46/46)
- `API_KEYS` env entries: `key`, `key:site`, or `key:siteA|siteB|...` — first = HOME site (all writes: discovery, learning, logs), full list = READ SCOPE.
- Reads filter `site_id = ANY(scope)`; non-home results penalised ×`CROSS_SITE_PENALTY` (0.85) in L0/L1; −0.5 in L3 ranking. Shared indexes deliberate via scopes; home wins ties.
- GitHub secret `NAV_API_KEYS` already updated to: `nav-9eadef81559f12263d150308a53b2975:default,nav-d240be1101a43aa295f1dc26fe77e7e7:lumo`.
- Widget carries key in `/navigate` body (sendBeacon can't set headers) and `&k=` on `/query/suggest`. Demo-site HTML already uses the lumo key; both S3 sites synced with newest widget.
- DB migration in `core/db.py` (idempotent): site_id on nav_index/nav_hot_paths/nav_query_log/nav_navigate_log, default 'default'; uniques now `(site_id,path)`.

## Key facts (avoid re-discovery)
- API: `https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com` · Lambda `portal-nav-api` (eu-west-1, VPC, no outbound internet)
- NovaSure portal: `https://dqto7bjc8xm6i.cloudfront.net` (CF `EQT6YWI25BMG2`, bucket `portal-nav-api-mock-684756697968`); deploy via `./mock-portal/deploy.sh` (auto-invalidates; sometimes exits 255 spuriously — retry)
- Lumo demo: `https://d6kupsfl5u4c6.cloudfront.net` (CF `E1KJRIM4W6FY0A`, bucket `lumo-travel-demo-684756697968`, root object `home.html`)
- Canonical widget: `widget/nav-widget.js` → ALWAYS copy to `mock-portal/assets/` + `demo-site/assets/` before syncing
- `gh` CLI broken (wrong npm package) — use GitHub REST with token from git remote URL
- Bash here-docs with complex quotes break — Write a .py file and run it; always `encoding='utf-8'` for read/write
- Cascade: NLU(intent strip+spell) → L0 hot/aliases → L1 embed → L2 rerank → L3 keywords/synonyms → L4 weak candidates → MISS. Learning: /navigate → alias on home site. Discovery: widget self-report + background same-origin crawl (max 30/session).
- AppSec workflow green; Trivy scans ECR `:latest` (don't rebuild).

## Feature backlog (user-approved direction)
- Analytics/click insights — parked, user may revive
- Miss-mining weekly report; CloudFront-Function edge injection (zero-touch install); landing-page inference learning
