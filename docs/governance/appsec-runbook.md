# AppSec Runbook — portal-nav-api

## Overview

portal-nav-api uses an open-source Veracode-equivalent AppSec pipeline.
Every push and PR triggers automated security scanning. Results appear in
the **GitHub Security** tab (Security → Code scanning alerts).

---

## Pipeline Jobs

| Job | Tool | Gate | When |
|-----|------|------|------|
| `sast` | CodeQL + Semgrep | CRITICAL → fail | Push + PR |
| `sca` | OWASP-DC + pip-audit + npm audit | CVSS ≥ 7 → fail | Push + PR |
| `secrets` | Gitleaks | Any secret → fail | Push + PR |
| `container` | Trivy | CRITICAL/HIGH → fail | Push + PR |
| `licence` | pip-licenses | GPL/AGPL/SSPL → fail | Push + PR |
| `dast` | OWASP ZAP | Advisory only | Weekly + manual |

---

## Responding to Findings

### CRITICAL (blocks merge)
1. Open the Security tab → Code scanning alerts.
2. Find the alert, click through to the file/line.
3. Determine: real finding or false positive?
   - **Real**: fix before merging. No exceptions.
   - **False positive**: add suppression to `.semgrep/` (Semgrep) or
     `appsec/owasp-dc-suppressions.xml` (OWASP-DC) with justification
     comment and sprint reference. Have a second engineer review.

### HIGH (warn, requires review comment)
- Add a PR comment acknowledging the finding.
- Either fix before merge or open a security ticket (sprint backlog).
- Do not suppress without documented justification.

### MEDIUM / LOW
- Advisory only. Tracked in Security tab.
- Review quarterly during AppSec review.

---

## Custom Semgrep Rules

Rules specific to this project live in `.semgrep/portal-nav-api-custom-rules.yml`.

Current rules:
- `portal-nav-hardcoded-credential` — detects literal API keys/tokens
- `portal-nav-db-uncaught-get-conn` — `get_conn()` without try/except
- `portal-nav-key-timing-unsafe` — `==` on credential (use `hmac.compare_digest`)
- `portal-nav-sql-injection` — string interpolation in `cursor.execute()`
- `portal-nav-console-log` — `print()` in application code
- `portal-nav-stack-trace-leak` — traceback in HTTP response body
- `portal-nav-bypass-settings` — `os.environ` direct access outside Settings class

To add a new rule: edit `.semgrep/portal-nav-api-custom-rules.yml`,
follow the existing pattern, include `cwe` and `owasp` metadata.

---

## DAST (ZAP)

ZAP baseline scan runs weekly (Monday 02:00 UTC) against the live API:
`https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com`

To run manually: GitHub Actions → AppSec → Run workflow.

ZAP policy is in `appsec/zap-rules.conf`. The API is stateless JSON —
browser-specific rules (CSP, cookies) are set to WARN not FAIL.

---

## Veracode Migration

When Veracode credentials arrive (`VERACODE_API_ID` + `VERACODE_API_KEY`):

1. Add both as GitHub repo secrets.
2. In `.github/workflows/appsec.yml`, replace the `sast` job body with:
   ```yaml
   - uses: veracode/veracode-uploadandscan-action@v1
     with:
       appname: portal-nav-api
       createprofile: true
       filepath: .
       vid: ${{ secrets.VERACODE_API_ID }}
       vkey: ${{ secrets.VERACODE_API_KEY }}
   ```
3. Remove the CodeQL and Semgrep steps from the `sast` job.
4. All other jobs (SCA, DAST, secrets, licence, container) remain unchanged.

---

## Quarterly Review Checklist

- [ ] Review and age out suppressed findings (remove expired ones)
- [ ] Update tool action versions (CodeQL, Trivy, ZAP, Gitleaks)
- [ ] Review MEDIUM/LOW findings in Security tab
- [ ] Check for new Semgrep rules that match recurring patterns
- [ ] Verify DAST target URL is still correct after any infrastructure change
