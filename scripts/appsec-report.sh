#!/usr/bin/env bash
# appsec-report.sh — Gate script: summarise SARIF findings and fail on CRITICAL.
# Usage: ./scripts/appsec-report.sh <sarif-file> [--fail-on CRITICAL|HIGH]
set -euo pipefail

SARIF_FILE="${1:-}"
FAIL_ON="${2:---fail-on}"
FAIL_LEVEL="${3:-CRITICAL}"

if [[ -z "$SARIF_FILE" || ! -f "$SARIF_FILE" ]]; then
  echo "Usage: $0 <sarif-file> [--fail-on CRITICAL|HIGH]"
  exit 1
fi

# Count findings by severity level
CRITICAL=$(python3 -c "
import json, sys
data = json.load(open('$SARIF_FILE'))
count = 0
for run in data.get('runs', []):
    for result in run.get('results', []):
        level = result.get('level', '')
        if level == 'error':
            count += 1
print(count)
")

HIGH=$(python3 -c "
import json, sys
data = json.load(open('$SARIF_FILE'))
count = 0
for run in data.get('runs', []):
    for result in run.get('results', []):
        level = result.get('level', '')
        if level == 'warning':
            count += 1
print(count)
")

echo "============================================================"
echo "AppSec Gate — $(basename "$SARIF_FILE")"
echo "  CRITICAL (error):  $CRITICAL"
echo "  HIGH (warning):    $HIGH"
echo "============================================================"

if [[ "$FAIL_LEVEL" == "CRITICAL" && "$CRITICAL" -gt 0 ]]; then
  echo "FAIL: $CRITICAL CRITICAL finding(s) — merge blocked."
  exit 1
fi

if [[ "$FAIL_LEVEL" == "HIGH" && ( "$CRITICAL" -gt 0 || "$HIGH" -gt 0 ) ]]; then
  echo "FAIL: $((CRITICAL + HIGH)) HIGH+ finding(s) — merge blocked."
  exit 1
fi

echo "PASS: No $FAIL_LEVEL+ findings."
