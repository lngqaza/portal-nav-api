'use strict';

/**
 * k6 load test for portal-nav-api.
 *
 * Stages:
 *   ramp-up  : 0→20 VUs over 30s   — verify no pool exhaustion at low concurrency
 *   soak     : 20 VUs for 2m        — sustained load: ONNX thread-safety + pool reuse
 *   spike    : 0→60 VUs over 10s    — burst: Lambda concurrency, pool timeout behaviour
 *   cool-down: 60→0 VUs over 20s    — pool drain + connection cleanup
 *
 * Required env vars (pass with -e):
 *   NAV_API_URL         — e.g. https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com
 *   NAV_API_KEY         — x-api-key value
 *   NAV_ADMIN_TOKEN     — Bearer token for admin endpoints
 *
 * Run:
 *   k6 run -e NAV_API_URL=https://... -e NAV_API_KEY=nav-... -e NAV_ADMIN_TOKEN=... \
 *       tests/load/k6-load-test.js
 *
 * Thresholds (gates — test fails if breached):
 *   p95 latency  < 500ms  for /query
 *   p99 latency  < 2000ms for /query
 *   error rate   < 1%
 *   MISS rate    < 20%    (too many MISSes = index not populated or thresholds misconfigured)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// ── Custom metrics ────────────────────────────────────────────────────────────
const missCount    = new Counter('nav_miss_total');
const missRate     = new Rate('nav_miss_rate');
const queryLatency = new Trend('nav_query_latency_ms', true);

// ── Config ────────────────────────────────────────────────────────────────────
const BASE_URL    = __ENV.NAV_API_URL    || 'https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com';
const API_KEY     = __ENV.NAV_API_KEY;
const ADMIN_TOKEN = __ENV.NAV_ADMIN_TOKEN;

if (!API_KEY) {
  throw new Error('NAV_API_KEY env var is required');
}

// Representative query mix drawn from common Sanlam Connect navigation intents.
const QUERIES = [
  'submit a claim',
  'renew my policy',
  'update my contact details',
  'make a payment',
  'download policy document',
  'log in to my account',
  'funeral cover',
  'life insurance quote',
  'find a financial adviser',
  'retirement annuity',
  'change beneficiary',
  'policy surrender value',
  'retrenchment benefit',
  'premium holiday',
  'group risk benefits',
];

const BATCH_QUERIES = [
  ['submit claim', 'renew policy'],
  ['make payment', 'update details', 'download document'],
];

// ── Thresholds ────────────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: '30s', target: 20 },  // ramp-up
    { duration: '2m',  target: 20 },  // soak
    { duration: '10s', target: 60 },  // spike
    { duration: '20s', target: 0  },  // cool-down
  ],
  thresholds: {
    'nav_query_latency_ms{scenario:default}': [
      'p(95)<500',
      'p(99)<2000',
    ],
    'http_req_failed': ['rate<0.01'],  // < 1% HTTP errors
    'nav_miss_rate':   ['rate<0.20'],  // < 20% MISS layer responses
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Pick a random element from an array. */
function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

const QUERY_HEADERS = {
  'Content-Type': 'application/json',
  'x-api-key': API_KEY,
};

const ADMIN_HEADERS = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${ADMIN_TOKEN}`,
};

// ── Main VU scenario ──────────────────────────────────────────────────────────

export default function () {
  const roll = Math.random();

  if (roll < 0.60) {
    // 60% — single /query (most common path, drives L0→L4 cascade)
    const q = pick(QUERIES);
    const start = Date.now();
    const res = http.post(
      `${BASE_URL}/query`,
      JSON.stringify({ query: q }),
      { headers: QUERY_HEADERS, tags: { name: '/query' } },
    );
    queryLatency.add(Date.now() - start);

    const ok = check(res, {
      'query 200': r => r.status === 200,
      'query has path or null': r => {
        try {
          const b = JSON.parse(r.body);
          return 'path' in b;
        } catch { return false; }
      },
    });

    if (ok) {
      try {
        const body = JSON.parse(res.body);
        const isMiss = body.layer === 'MISS' || body.path === null;
        missRate.add(isMiss ? 1 : 0);
        if (isMiss) missCount.add(1);
      } catch { /* non-JSON body counted as error already */ }
    }

  } else if (roll < 0.80) {
    // 20% — /query/batch (exercises ThreadPoolExecutor + dedup)
    const queries = pick(BATCH_QUERIES);
    const res = http.post(
      `${BASE_URL}/query/batch`,
      JSON.stringify({ queries }),
      { headers: QUERY_HEADERS, tags: { name: '/query/batch' } },
    );
    check(res, {
      'batch 200': r => r.status === 200,
      'batch array response': r => {
        try { return Array.isArray(JSON.parse(r.body)); }
        catch { return false; }
      },
    });

  } else if (roll < 0.90) {
    // 10% — /query/suggest (label prefix, no auth required)
    const prefix = pick(QUERIES).split(' ')[0];
    const res = http.get(
      `${BASE_URL}/query/suggest?q=${encodeURIComponent(prefix)}`,
      { tags: { name: '/query/suggest' } },
    );
    check(res, {
      'suggest 200': r => r.status === 200,
    });

  } else if (roll < 0.95) {
    // 5% — /health (liveness probe baseline)
    const res = http.get(`${BASE_URL}/health`, { tags: { name: '/health' } });
    check(res, { 'health 200': r => r.status === 200 });

  } else if (ADMIN_TOKEN) {
    // 5% — /admin/stats (read-only admin, exercises auth + DB)
    const res = http.get(
      `${BASE_URL}/admin/stats`,
      { headers: ADMIN_HEADERS, tags: { name: '/admin/stats' } },
    );
    check(res, { 'admin/stats 200': r => r.status === 200 });
  }

  sleep(0.5 + Math.random() * 0.5);  // 0.5–1s think time
}

// ── Setup: verify service is reachable before load starts ─────────────────────
export function setup() {
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Health check failed before load test: status=${res.status}`);
  }
  console.log(`Load test starting against: ${BASE_URL}`);
}
