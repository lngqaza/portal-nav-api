# HANDOVER — portal-nav-api: multi-tenancy rollout (resume point)

**Session name suggestion:** `portal-nav: finish multi-tenancy deploy + verify`
**Date:** 2026-06-11 · Repo: `lngqaza/portal-nav-api` (branch `master`) · Local: `C:\Users\e1000836\Desktop\portal-nav-api`
**Efficiency rules:** hyper token economy — batch calls, poll deploys with single curl, no re-reads, terse output. Full-auto: bypass-permissions is set globally AND in project .claude/settings.json — no prompts.

## ⚠️ FULL-AUTO SETUP — READ FIRST

`bypassPermissions` + `skipDangerousModePermissionPrompt: true` is set in BOTH:
- `C:\Users\e1000836\.claude\settings.json` (global)
- `C:\Users\e1000836\Desktop\portal-nav-api\.claude\settings.json` (project)

**If you still see permission prompts:** the session was not restarted after the settings change. Tell the user to close and reopen Claude Code, then resume with this handover.

**Never use `dangerouslyDisableSandbox: true`** on Bash calls — unnecessary on Windows and may trigger extra dialogs.

## ⚠️ IMMEDIATE NEXT STEP — verify deploy succeeded

Last push: commit `71553d7` (added .claude/settings.json). Before that: `4928310` fixed the Lambda env vars bug.
The deploy workflow should have run on `4928310`. Check it:

```python
# Run this as a .py file (heredocs break on Windows UTF-8)
import urllib.request, json, sys
TOKEN = "ghp_REDACTED"
for run_id in ["latest"]:
    req = urllib.request.Request(
        "https://api.github.com/repos/lngqaza/portal-nav-api/actions/workflows/deploy-nav-api.yml/runs?per_page=3",
        headers={"Authorization": f"token {TOKEN}", "User-Agent": "python"}
    )
    with urllib.request.urlopen(req) as r:
        runs = json.load(r)["workflow_runs"]
    for r in runs:
        print(r["id"], r.get("conclusion") or "running", r["head_sha"][:8])
```

Save as `check_runs.py` and run: `python3 check_runs.py`

If the run on `4928310` failed again, get job logs:
```python
# check_jobs.py already exists at C:\Users\e1000836\Desktop\check_jobs.py
# Usage: python3 C:/Users/e1000836/Desktop/check_jobs.py <RUN_ID>
```

If it succeeded, proceed to the rollout steps below.

## What was fixed this session

The deploy on commit `bba90b3` / `332aff8e` failed with:
```
aws: [ERROR]: An error occurred (ParamValidation): Error parsing parameter '--environment':
Expected: '=', received: ',' for input: Variables={DATABASE_URL=***,API_KEYS=***,...}
```
**Root cause:** `API_KEYS` secret now contains a comma (`nav-xxx:default,nav-xxx:lumo`) — the AWS CLI shorthand `Variables={K=V,K=V}` treats commas as delimiters. Fixed in commit `4928310` by switching to JSON format via single-line `python3 -c`.

## After deploy succeeds — remaining rollout steps (in order)

1. **Verify migration applied** — hit `/health`, then any `/query`. The `site_id` columns + `(site_id,path)` uniques are created idempotently at Lambda startup by `core/db.py`.

2. **Clean stale Lumo rows from 'default' site** (pre-date tenancy):
   - Get ADMIN_TOKEN: `aws lambda get-function-configuration --function-name portal-nav-api --region eu-west-1 --query 'Environment.Variables.ADMIN_TOKEN' --output text`
   - `GET https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com/admin/index?limit=200` (Bearer token)
   - Delete rows for paths: `/home.html /flights.html /hotels.html /bookings.html /contact-us.html`
   - `DELETE /admin/index/{id}` for each
   - Also check `nav_hot_paths` for `/claims-new.html` alias rows — leave NovaSure ones

3. **Re-crawl Lumo under its own tenant** — open `https://d6kupsfl5u4c6.cloudfront.net/home.html` in a new tab via Claude-in-Chrome MCP. Widget auto-crawls all 5 pages → site `lumo`. Use a fresh/incognito tab (sessionStorage dedupe may suppress re-discovery).

4. **Verify isolation + boost** (single batch):
   - Lumo key `nav-d240be1101a43aa295f1dc26fe77e7e7`: "talk to a travel agent" → must return `/contact-us.html` (LUMO), NOT NovaSure `/support.html`
   - NovaSure key `nav-9eadef81559f12263d150308a53b2975`: "where to log claims" → `/claims-new.html` L0
   - Lumo typo test: "canccel my trip" → `/bookings.html`

5. **Update demo-site/ACTIVATION_GUIDE.md** — replace shared-index limitation note with scope syntax (`key:siteA|siteB`, home site first, `CROSS_SITE_PENALTY=0.85`). Then:
   ```bash
   aws s3 sync demo-site s3://lumo-travel-demo-684756697968
   aws cloudfront create-invalidation --distribution-id E1KJRIM4W6FY0A --paths "/*"
   ```
   Commit all changes.

## Key facts (avoid re-discovery)

- API: `https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com` · Lambda `portal-nav-api` (eu-west-1, VPC)
- NovaSure portal: `https://dqto7bjc8xm6i.cloudfront.net` (CF `EQT6YWI25BMG2`, bucket `portal-nav-api-mock-684756697968`); deploy via `./mock-portal/deploy.sh`
- Lumo demo: `https://d6kupsfl5u4c6.cloudfront.net` (CF `E1KJRIM4W6FY0A`, bucket `lumo-travel-demo-684756697968`)
- Canonical widget: `widget/nav-widget.js` → ALWAYS copy to `mock-portal/assets/` + `demo-site/assets/` before syncing
- GitHub token: in git remote URL — `git remote get-url origin` extracts it
- `gh` CLI broken (wrong npm package) — use GitHub REST API with token
- Bash heredocs with complex quotes break on Windows — always write a `.py` file and run it; always `encoding='utf-8'`
- Deploy.sh sometimes exits 255 spuriously — retry if it does
- Always sync widget to BOTH sites

## What multi-tenancy IS (built, committed, all 46 tests green)

- `API_KEYS` env: `key`, `key:site`, or `key:siteA|siteB|...` — first = HOME site
- Reads filter `site_id = ANY(scope)`; cross-site results penalised ×0.85 in L0/L1; −0.5 in L3
- `NAV_API_KEYS` secret: `nav-9eadef81559f12263d150308a53b2975:default,nav-d240be1101a43aa295f1dc26fe77e7e7:lumo`
- DB migration in `core/db.py` (idempotent): `site_id` on all 4 tables, default `'default'`

## Feature backlog (user-approved, parked)

- Analytics/click insights
- Miss-mining weekly report
- CloudFront-Function edge injection (zero-touch install)
- Landing-page inference learning
