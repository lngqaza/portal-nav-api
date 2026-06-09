#!/usr/bin/env bash
# load-test.sh — Baseline load test against the live portal-nav-api endpoint.
# Sends 200 queries (10 concurrent) and prints a p50/p95/p99 latency summary.
#
# Usage:
#   NAV_API_KEY="nav-..." ./scripts/load-test.sh
#   optional: CONCURRENCY=20 TOTAL=500 ./scripts/load-test.sh
#
# Requirements: curl, awk, sort (all present on macOS/Linux/WSL)
# Does NOT require hey/ab/k6.

set -euo pipefail

BASE_URL="${NAV_BASE_URL:-https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com}"
API_KEY="${NAV_API_KEY:?NAV_API_KEY must be set}"
CONCURRENCY="${CONCURRENCY:-10}"
TOTAL="${TOTAL:-200}"

# Representative queries covering all layers of the cascade
QUERIES=(
  "submit a claim"
  "check claim status"
  "renew my policy"
  "make a payment"
  "change my password"
  "contact support"
  "view my documents"
  "health benefits"
  "tax certificate"
  "life cover options"
  "cancel my policy"
  "payment history"
  "upload documents"
  "live chat"
  "lodge a complaint"
  "vehicle insurance"
  "home contents"
  "beneficiary"
  "direct debit"
  "asdfqwer unknown query xyz"
)

QUERY_COUNT="${#QUERIES[@]}"
TMPDIR_RESULTS=$(mktemp -d)
trap 'rm -rf "$TMPDIR_RESULTS"' EXIT

echo "=== portal-nav-api load test ==="
echo "  endpoint:    $BASE_URL/query"
echo "  total:       $TOTAL requests"
echo "  concurrency: $CONCURRENCY"
echo "  queries:     $QUERY_COUNT rotating"
echo ""

run_single() {
  local idx="$1"
  local query="${QUERIES[$((idx % QUERY_COUNT))]}"
  local body
  body=$(printf '{"query":"%s"}' "$query")

  local t0 t1 elapsed status layer
  t0=$(date +%s%3N)
  local response
  response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/query" \
    -H "x-api-key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$body" 2>/dev/null)
  t1=$(date +%s%3N)
  elapsed=$((t1 - t0))

  status=$(echo "$response" | tail -1)
  layer=$(echo "$response" | head -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('layer','?'))" 2>/dev/null || echo "err")

  echo "$elapsed $status $layer" >> "$TMPDIR_RESULTS/results.txt"
}

export -f run_single
export BASE_URL API_KEY QUERY_COUNT
export QUERIES_STR="${QUERIES[*]}"

# Run with xargs for concurrency (portable, no GNU parallel required)
seq 0 $((TOTAL - 1)) | xargs -P "$CONCURRENCY" -I{} bash -c 'run_single "$@"' _ {}

echo "=== Results ==="

python3 - "$TMPDIR_RESULTS/results.txt" <<'EOF'
import sys, statistics

lines = open(sys.argv[1]).readlines()
latencies = []
status_counts = {}
layer_counts = {}
errors = 0

for line in lines:
    parts = line.strip().split()
    if len(parts) < 3:
        errors += 1
        continue
    ms, status, layer = int(parts[0]), parts[1], parts[2]
    latencies.append(ms)
    status_counts[status] = status_counts.get(status, 0) + 1
    layer_counts[layer] = layer_counts.get(layer, 0) + 1

if not latencies:
    print("No results collected.")
    sys.exit(1)

latencies.sort()
n = len(latencies)

def pct(p):
    idx = int(n * p / 100)
    return latencies[min(idx, n-1)]

print(f"  Requests:  {n}")
print(f"  Errors:    {errors}")
print(f"  Min:       {min(latencies)} ms")
print(f"  p50:       {pct(50)} ms")
print(f"  p90:       {pct(90)} ms")
print(f"  p95:       {pct(95)} ms")
print(f"  p99:       {pct(99)} ms")
print(f"  Max:       {max(latencies)} ms")
print(f"  Mean:      {statistics.mean(latencies):.0f} ms")
print()
print("  HTTP status breakdown:")
for s, c in sorted(status_counts.items()):
    print(f"    {s}: {c} ({100*c/n:.1f}%)")
print()
print("  Layer breakdown:")
for l, c in sorted(layer_counts.items()):
    print(f"    {l}: {c} ({100*c/n:.1f}%)")
EOF
