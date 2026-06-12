'use strict';

/**
 * Wave 3 — Contract: api-shape.test.js
 *
 * Validates JSON response shapes at the HTTP level against the live API Gateway.
 *
 * Skip discipline:
 *   SHAPE-01, SHAPE-12, SHAPE-13  — no credentials needed (health + 401 probes)
 *   All other suites               — conditional describe.skip when creds absent
 */

const fetch = require('node-fetch');
const {
  BASE_URL,
  CREDS_OK,
  SKIP_REASON,
  query,
  queryBatch,
  suggest,
  health,
  adminGet,
  rawPost,
} = require('../helpers/client');

const REQUIRED_FIELDS = ['path', 'label', 'confidence', 'layer', 'response_ms', 'candidates', 'suggestion'];
const VALID_LAYERS    = ['L0', 'L1', 'L2', 'L3', 'L4', 'MISS'];

// ── SHAPE-01 — health check (no auth) ────────────────────────────────────────

describe('SHAPE-01: GET /health', () => {
  test('returns HTTP 200 with { status: "ok" }', async () => {
    const { status, body } = await health();
    expect(status).toBe(200);
    expect(body.status).toBe('ok');
  });
});

// ── SHAPE-12/13 — unauthenticated error codes (no creds needed) ──────────────

describe('SHAPE-12/13: missing credentials return 401', () => {
  test('SHAPE-12: POST /query without x-api-key → 401', async () => {
    const { status } = await rawPost('/query', JSON.stringify({ query: 'test' }), {
      'Content-Type': 'application/json',
    });
    expect(status).toBe(401);
  });

  test('SHAPE-13: GET /admin/stats without Authorization → 401', async () => {
    const res = await fetch(`${BASE_URL}/admin/stats`);
    expect(res.status).toBe(401);
  });
});

// ── Authenticated query shape tests ──────────────────────────────────────────

(CREDS_OK ? describe : describe.skip)(
  `Query response shape${CREDS_OK ? '' : SKIP_REASON}`,
  () => {
    test('SHAPE-02: POST /query returns all 7 required fields', async () => {
      const { status, body } = await query('submit a claim');
      expect(status).toBe(200);
      REQUIRED_FIELDS.forEach(f => expect(body).toHaveProperty(f));
    });

    test('SHAPE-03: confidence is a number in [0, 1]', async () => {
      const { body } = await query('submit a claim');
      expect(typeof body.confidence).toBe('number');
      expect(body.confidence).toBeGreaterThanOrEqual(0);
      expect(body.confidence).toBeLessThanOrEqual(1);
    });

    test('SHAPE-04: layer is one of L0 | L1 | L2 | MISS', async () => {
      const { body } = await query('submit a claim');
      expect(VALID_LAYERS).toContain(body.layer);
    });

    test('SHAPE-05: response_ms is a non-negative integer', async () => {
      const { body } = await query('submit a claim');
      expect(Number.isInteger(body.response_ms)).toBe(true);
      expect(body.response_ms).toBeGreaterThanOrEqual(0);
    });

    test('SHAPE-06: candidates is an array', async () => {
      const { body } = await query('submit a claim');
      expect(Array.isArray(body.candidates)).toBe(true);
    });

    test('SHAPE-07: suggestion is null or a string', async () => {
      const { body } = await query('submit a claim');
      expect(
        body.suggestion === null || typeof body.suggestion === 'string'
      ).toBe(true);
    });

    test('SHAPE-14: POST /query with empty string → 400', async () => {
      const { status } = await query('');
      expect(status).toBe(400);
    });
  }
);

// ── Batch shape tests ─────────────────────────────────────────────────────────

(CREDS_OK ? describe : describe.skip)(
  `Batch response shape${CREDS_OK ? '' : SKIP_REASON}`,
  () => {
    test('SHAPE-08: POST /query/batch returns array; each item has all 7 fields', async () => {
      const { status, body } = await queryBatch(['submit a claim', 'renew policy']);
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
      body.forEach((item, i) => {
        REQUIRED_FIELDS.forEach(f =>
          expect(item).toHaveProperty(f, undefined, `result[${i}] missing "${f}"`)
        );
      });
    });

    test('SHAPE-15: POST /query/batch with 21 queries → 400', async () => {
      const { status } = await queryBatch(Array.from({ length: 21 }, (_, i) => `q${i}`));
      expect(status).toBe(400);
    });
  }
);

// ── Suggest shape tests — no auth required ────────────────────────────────────

describe('SHAPE-09: GET /query/suggest response shape', () => {
  test('returns an array of { path, label } objects', async () => {
    const { status, body } = await suggest('claim');
    expect(status).toBe(200);
    expect(Array.isArray(body)).toBe(true);
    body.forEach((item, i) => {
      expect(typeof item.path).toBe('string', `suggest[${i}] path must be string`);
      expect(typeof item.label).toBe('string', `suggest[${i}] label must be string`);
    });
  });
});

// ── Admin shape tests ─────────────────────────────────────────────────────────

(CREDS_OK ? describe : describe.skip)(
  `Admin response shapes${CREDS_OK ? '' : SKIP_REASON}`,
  () => {
    test('SHAPE-10: GET /admin/config returns threshold fields', async () => {
      const { status, body } = await adminGet('/admin/config');
      expect(status).toBe(200);
      ['MAX_HOT_PATHS', 'HOT_PATH_THRESHOLD', 'L1_THRESHOLD', 'L2_THRESHOLD'].forEach(f =>
        expect(body).toHaveProperty(f)
      );
    });

    test('SHAPE-11: GET /admin/stats returns total_queries_24h, layers, top_misses', async () => {
      const { status, body } = await adminGet('/admin/stats');
      expect(status).toBe(200);
      expect(typeof body.total_queries_24h).toBe('number');
      expect(typeof body.layers).toBe('object');
      expect(Array.isArray(body.top_misses)).toBe(true);
    });

    test('SHAPE-16: GET /admin/audit-log returns an array', async () => {
      const { status, body } = await adminGet('/admin/audit-log?limit=5');
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
    });

    test('SHAPE-17: GET /admin/audit-log rows have required fields', async () => {
      const { status, body } = await adminGet('/admin/audit-log?limit=5');
      expect(status).toBe(200);
      if (body.length > 0) {
        ['id', 'site_id', 'action', 'resource', 'created_at'].forEach(f =>
          expect(body[0]).toHaveProperty(f)
        );
      }
    });

    test('SHAPE-18: GET /admin/aliases returns an array', async () => {
      const { status, body } = await adminGet('/admin/aliases?limit=5');
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
    });

    test('SHAPE-19: GET /admin/aliases rows have required fields', async () => {
      const { status, body } = await adminGet('/admin/aliases?limit=5');
      expect(status).toBe(200);
      if (body.length > 0) {
        ['id', 'site_id', 'old_path', 'new_path', 'created_at'].forEach(f =>
          expect(body[0]).toHaveProperty(f)
        );
      }
    });

    test('SHAPE-20: POST /admin/aliases returns id, old_path, new_path', async () => {
      const ts = Date.now();
      const { status, body } = await adminPost('/admin/aliases', {
        site: 'default',
        old_path: `/shape-test-old-${ts}`,
        new_path: `/shape-test-new-${ts}`,
      });
      expect(status).toBe(200);
      expect(body).toHaveProperty('id');
      expect(body).toHaveProperty('old_path');
      expect(body).toHaveProperty('new_path');
      // clean up
      if (body.id) await adminGet(`/admin/aliases/${body.id}`);
    });

    test('SHAPE-21: GET /admin/aliases supports limit and offset pagination', async () => {
      const { status, body } = await adminGet('/admin/aliases?limit=2&offset=0');
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
      expect(body.length).toBeLessThanOrEqual(2);
    });
  }
);
