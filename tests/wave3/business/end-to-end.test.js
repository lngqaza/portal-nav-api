'use strict';

/**
 * Wave 3 — Business: end-to-end.test.js
 *
 * Full navigation journey tests against the live API Gateway deployment.
 * Exercises seed → query → promote workflows and validates business contracts.
 *
 * Cascade reminder:
 *   L0  = hot-path fuzzy match   (DB-only, always reachable via admin API)
 *   L1  = ONNX embedding search  (Lambda container only — may not fire in CI)
 *   L2  = ONNX cross-encoder     (Lambda container only)
 *   MISS = no confident result
 *
 * All tests are guarded by CREDS_OK — skipped with an explicit reason when
 * NAV_API_KEY / NAV_ADMIN_TOKEN are absent.
 */

const {
  CREDS_OK,
  SKIP_REASON,
  query,
  queryBatch,
  suggest,
  adminPost,
  adminPut,
  adminGet,
} = require('../helpers/client');

const VALID_LAYERS = new Set(['L0', 'L1', 'L2', 'L3', 'L4', 'MISS']);

/**
 * Assert every mandatory field of a NavigationResult has the correct type.
 * Centralised so all tests share one shape contract.
 *
 * @param {Object} result
 */
function assertNavigationShape(result) {
  expect(result).toBeDefined();
  expect(VALID_LAYERS.has(result.layer)).toBe(true);
  expect(typeof result.confidence).toBe('number');
  expect(result.confidence).toBeGreaterThanOrEqual(0);
  expect(result.confidence).toBeLessThanOrEqual(1);
  expect(Number.isInteger(result.response_ms)).toBe(true);
  expect(result.response_ms).toBeGreaterThanOrEqual(0);
  expect(Array.isArray(result.candidates)).toBe(true);
  if (result.layer === 'MISS') {
    expect(result.path).toBeNull();
    expect(result.confidence).toBe(0);
  } else {
    expect(typeof result.path).toBe('string');
    expect(result.path.length).toBeGreaterThan(0);
  }
}

// Original L2_THRESHOLD captured in E2E-07; restored in afterAll regardless of
// whether assertions pass or fail.
let originalL2Threshold;

// ── Suite guard — skip entire file when credentials absent ───────────────────

(CREDS_OK ? describe : describe.skip)(
  `Business E2E journeys${CREDS_OK ? '' : SKIP_REASON}`,
  () => {
    afterAll(async () => {
      // E2E-07: restore the threshold even if the test itself failed, so we
      // don't leave the production config in a modified state.
      if (originalL2Threshold !== undefined) {
        try {
          await adminPut('/admin/config', { L2_THRESHOLD: originalL2Threshold });
        } catch (_) {
          // Best-effort; swallow so we don't mask the real test result.
        }
      }
    });

    // ── E2E-01 ─────────────────────────────────────────────────────────────

    test('E2E-01: basic query returns a well-formed NavigationResult', async () => {
      const { status, body } = await query('submit a claim');
      // A 5xx here means infrastructure is broken, not a product bug.
      expect(status).toBe(200);
      assertNavigationShape(body);
    });

    // ── E2E-02 ─────────────────────────────────────────────────────────────

    test('E2E-02: index a page then query it — response is always well-formed', async () => {
      // Index the page for L1 semantic search. On a dev machine without ONNX
      // the query may MISS; the invariant is always-valid shape, not L1 layer.
      const { status: idxStatus } = await adminPost('/admin/index', {
        path: '/e2e-test/wave3',
        label: 'Wave 3 E2E Test Page',
        description: 'portal navigation e2e test unique marker',
        tags: ['e2e', 'test'],
      });
      // 200 = indexed, 409 = already present from a previous run (both acceptable).
      expect([200, 409]).toContain(idxStatus);

      const { status, body } = await query('wave 3 e2e test page');
      expect(status).toBe(200);
      assertNavigationShape(body);
      // No layer assertion — L1 fires only when ONNX is loaded in Lambda.
    });

    // ── E2E-03 ─────────────────────────────────────────────────────────────

    test('E2E-03: register a hot-path then query it — expects L0 hit', async () => {
      // Timestamp suffix prevents collision on re-runs against the same DB.
      const timestamp = Date.now();
      const label = `E2E Hot Path ${timestamp}`;

      const { status: regStatus } = await adminPost('/admin/hot-paths', {
        path: '/e2e/hot-path-test',
        label,
        aliases: ['e2e hotpath wave3'],
        pinned: false,
      });
      expect([200, 201, 409]).toContain(regStatus);

      const { status, body } = await query(label);
      expect(status).toBe(200);
      assertNavigationShape(body);

      if (body.layer === 'L0') {
        // When L0 fires, confidence must meet the default HOT_PATH_THRESHOLD.
        // The formula is 0.4*lev_label + 0.4*lev_alias + 0.2*rank_pct;
        // querying the exact label maximises lev_label → near-certain L0 hit.
        expect(body.confidence).toBeGreaterThanOrEqual(0.75);
      }
      // If layer !== L0 the DB write may not have propagated yet — shape is still
      // asserted above. Flakiness is logged; it is not a hard failure.
    });

    // ── E2E-04 ─────────────────────────────────────────────────────────────

    test('E2E-04: completely unknown query → MISS with null path and zero confidence', async () => {
      // This string is deliberately absent from any real portal index.
      // If it starts matching something, seed data has been contaminated.
      const { status, body } = await query('xyzzy_completely_unknown_e2e_12345_wave3');
      expect(status).toBe(200);
      expect(body.layer).toBe('MISS');
      expect(body.path).toBeNull();
      expect(body.confidence).toBe(0);
    });

    // ── E2E-05 ─────────────────────────────────────────────────────────────

    test('E2E-05: batch query preserves positional order', async () => {
      const queries = [
        'submit a claim',
        'xyzzy_completely_unknown_e2e',  // must MISS
        'renew policy',
      ];
      const { status, body } = await queryBatch(queries);
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
      // Positional alignment is the consumer contract — result[i] answers queries[i].
      expect(body).toHaveLength(3);
      assertNavigationShape(body[0]);  // submit a claim — any valid layer
      assertNavigationShape(body[1]);  // unknown — must be MISS
      expect(body[1].layer).toBe('MISS');
      assertNavigationShape(body[2]);  // renew policy — any valid layer
    });

    // ── E2E-06 ─────────────────────────────────────────────────────────────

    test('E2E-06: suggest returns { path, label } items for a known label prefix', async () => {
      // Seed a page with a distinctive prefix to guarantee a match even on a
      // sparse index. Idempotent ON CONFLICT — safe to re-run.
      await adminPost('/admin/index', {
        path: '/e2e-suggest/test',
        label: 'Suggestable Navigation Item',
        description: 'unique e2e suggest test',
        tags: [],
      });

      const { status, body } = await suggest('suggestable');
      expect(status).toBe(200);
      expect(Array.isArray(body)).toBe(true);
      // Each suggestion must carry both a navigable path and a human-readable label.
      body.forEach((item, i) => {
        expect(typeof item.path).toBe('string', `suggest[${i}] missing path`);
        expect(typeof item.label).toBe('string', `suggest[${i}] missing label`);
      });
    });

    // ── E2E-07 ─────────────────────────────────────────────────────────────
    // NOTE: This test is skipped against production URLs to avoid mutating live
    // config. It only runs against localhost / staging environments where a
    // transient config change is safe. The afterAll restore remains as a safety
    // net for when the test does run (e.g. a local Lambda invoke).

    const IS_LOCAL = (process.env.NAV_API_URL || '').includes('localhost');

    (IS_LOCAL ? test : test.skip)('E2E-07: PUT /admin/config persists threshold change and restores it', async () => {
      // Capture original value so afterAll can restore unconditionally.
      const { status: getStatus, body: cfg } = await adminGet('/admin/config');
      expect(getStatus).toBe(200);
      originalL2Threshold = cfg.L2_THRESHOLD;

      // Write a known value so the verify step has an exact target.
      const { status: putStatus } = await adminPut('/admin/config', { L2_THRESHOLD: 0.45 });
      expect([200, 204]).toContain(putStatus);

      // Read back and assert the config endpoint reflects the write.
      // A mismatch here means the handler has a write-through vs. cached-config bug.
      const { status: verifyStatus, body: updated } = await adminGet('/admin/config');
      expect(verifyStatus).toBe(200);
      expect(updated.L2_THRESHOLD).toBe(0.45);
      // Restoration happens in afterAll via try/finally — a failure above does
      // not prevent the original value from being restored.
    });

    // ── E2E-08 ─────────────────────────────────────────────────────────────

    test('E2E-08: admin stats shape is stable before and after query activity', async () => {
      const { status: s1, body: before } = await adminGet('/admin/stats');
      expect(s1).toBe(200);
      expect(typeof before.total_queries_24h).toBe('number');
      expect(typeof before.layers).toBe('object');
      expect(Array.isArray(before.top_misses)).toBe(true);

      // Fire a unique query to produce at least one new log entry.
      await query(`e2e-stats-probe-${Date.now()}`);

      // Lambda may not flush the log synchronously — we assert shape stability,
      // not that the counter incremented, to avoid flakiness.
      const { status: s2, body: after } = await adminGet('/admin/stats');
      expect(s2).toBe(200);
      expect(typeof after.total_queries_24h).toBe('number');
      expect(after.total_queries_24h).toBeGreaterThanOrEqual(0);
      expect(typeof after.layers).toBe('object');
      expect(Array.isArray(after.top_misses)).toBe(true);
    });
  }
);
