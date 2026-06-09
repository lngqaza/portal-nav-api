#!/usr/bin/env python3
"""
load_test.py — Baseline load test against the live portal-nav-api endpoint.

Usage:
    NAV_API_KEY="nav-..." python3 scripts/load_test.py
    NAV_API_KEY="nav-..." python3 scripts/load_test.py --total 500 --concurrency 20

Requires: Python 3.9+ (stdlib only — urllib, threading, statistics)
No external dependencies.
"""
import argparse
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import json

BASE_URL = os.environ.get("NAV_BASE_URL", "https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com")
API_KEY  = os.environ.get("NAV_API_KEY", "")

QUERIES = [
    "submit a claim",
    "check claim status",
    "renew my policy",
    "make a payment",
    "change my password",
    "contact support",
    "view my documents",
    "health benefits",
    "tax certificate",
    "life cover options",
    "cancel my policy",
    "payment history",
    "upload documents",
    "live chat",
    "lodge a complaint",
    "vehicle insurance",
    "home contents",
    "beneficiary",
    "direct debit",
    "asdfqwer unknown query xyz",
]

results_lock = threading.Lock()
results      = []          # list of (latency_ms, status_code, layer)


def do_request(idx: int) -> None:
    query = QUERIES[idx % len(QUERIES)]
    body  = json.dumps({"query": query}).encode()
    req   = urllib.request.Request(
        f"{BASE_URL}/query",
        data=body,
        method="POST",
        headers={
            "x-api-key":     API_KEY,
            "Content-Type":  "application/json",
            "Content-Length": str(len(body)),
        },
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            raw        = resp.read()
            data       = json.loads(raw)
            layer      = data.get("layer", "?")
            status     = resp.status
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        status     = exc.code
        layer      = "err"
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        status     = 0
        layer      = "exc"
        print(f"  [exc] {exc}", file=sys.stderr)

    with results_lock:
        results.append((elapsed_ms, status, layer))


def run(total: int, concurrency: int) -> None:
    if not API_KEY:
        sys.exit("NAV_API_KEY is not set")

    print(f"=== portal-nav-api load test ===")
    print(f"  endpoint:    {BASE_URL}/query")
    print(f"  total:       {total} requests")
    print(f"  concurrency: {concurrency}")
    print(f"  queries:     {len(QUERIES)} rotating")
    print()

    semaphore = threading.Semaphore(concurrency)

    def worker(idx: int):
        with semaphore:
            do_request(idx)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(total)]
    t_start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_ms = int((time.monotonic() - t_start) * 1000)

    latencies     = [r[0] for r in results]
    status_counts: dict[int, int] = {}
    layer_counts:  dict[str, int] = {}
    for _, s, l in results:
        status_counts[s] = status_counts.get(s, 0) + 1
        layer_counts[l]  = layer_counts.get(l,  0) + 1

    latencies.sort()
    n = len(latencies)

    def pct(p: float) -> int:
        return latencies[min(int(n * p / 100), n - 1)]

    print("=== Results ===")
    print(f"  Wall clock:  {wall_ms} ms  ({wall_ms/1000:.1f}s)")
    print(f"  Requests:    {n}")
    print(f"  Min:         {min(latencies)} ms")
    print(f"  p50:         {pct(50)} ms")
    print(f"  p90:         {pct(90)} ms")
    print(f"  p95:         {pct(95)} ms")
    print(f"  p99:         {pct(99)} ms")
    print(f"  Max:         {max(latencies)} ms")
    print(f"  Mean:        {statistics.mean(latencies):.0f} ms")
    print()
    print("  HTTP status breakdown:")
    for s, c in sorted(status_counts.items()):
        print(f"    {s}: {c:3d}  ({100*c/n:.1f}%)")
    print()
    print("  Layer breakdown:")
    for l, c in sorted(layer_counts.items()):
        print(f"    {l}: {c:3d}  ({100*c/n:.1f}%)")
    print()

    error_count = sum(c for s, c in status_counts.items() if s not in (200, 201))
    if error_count > 0:
        print(f"WARNING: {error_count} non-2xx responses", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="portal-nav-api load test")
    parser.add_argument("--total",       type=int, default=200, help="Total requests (default 200)")
    parser.add_argument("--concurrency", type=int, default=10,  help="Concurrent threads (default 10)")
    args = parser.parse_args()
    run(args.total, args.concurrency)
