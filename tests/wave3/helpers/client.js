'use strict';

const fetch = require('node-fetch');

/**
 * Environment configuration for Wave 3 integration tests.
 * NAV_API_URL defaults to the deployed API Gateway endpoint.
 * NAV_API_KEY and NAV_ADMIN_TOKEN must be set explicitly — no defaults.
 */
const BASE_URL    = process.env.NAV_API_URL || 'https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com';
const apiKey      = process.env.NAV_API_KEY;
const adminToken  = process.env.NAV_ADMIN_TOKEN;

/**
 * True when both credentials are present.
 * Use with Jest's conditional describe/test:
 *   (CREDS_OK ? describe : describe.skip)('suite', () => { ... })
 *   (CREDS_OK ? test : test.skip)('case', async () => { ... })
 *
 * This is evaluated at registration time so Jest reports the skips correctly
 * (as skipped, not failed), and the reason is visible in the output.
 */
const CREDS_OK = Boolean(apiKey && adminToken);

/**
 * Standard skip reason for integration-pending tests.
 * Append to the describe/test name so it appears in `jest --verbose` output.
 */
const SKIP_REASON = ' [integration-pending: set NAV_API_KEY + NAV_ADMIN_TOKEN from Lambda env vars]';

/**
 * POST /query — navigate via the 3-layer cascade.
 *
 * @param {string} q - Navigation query text
 * @param {Object} [opts]
 * @param {string} [opts.apiKey] - Override the default API key
 * @returns {Promise<{status: number, body: Object}>}
 */
const query = async (q, opts = {}) => {
  const key = opts.apiKey ?? apiKey;
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': key },
    body: JSON.stringify({ query: q }),
  });
  return { status: res.status, body: await res.json() };
};

/**
 * POST /query/batch — navigate multiple queries in one call.
 *
 * @param {string[]} queries
 * @param {Object} [opts]
 * @param {string} [opts.apiKey]
 * @returns {Promise<{status: number, body: Object}>}
 */
const queryBatch = async (queries, opts = {}) => {
  const key = opts.apiKey ?? apiKey;
  const res = await fetch(`${BASE_URL}/query/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': key },
    body: JSON.stringify({ queries }),
  });
  return { status: res.status, body: await res.json() };
};

/**
 * GET /query/suggest?q=<q> — unauthenticated label prefix search.
 *
 * @param {string} q
 * @returns {Promise<{status: number, body: Object}>}
 */
const suggest = async (q) => {
  const res = await fetch(`${BASE_URL}/query/suggest?q=${encodeURIComponent(q)}`);
  return { status: res.status, body: await res.json() };
};

/**
 * GET /health — liveness probe, no auth required.
 *
 * @returns {Promise<{status: number, body: Object}>}
 */
const health = async () => {
  const res = await fetch(`${BASE_URL}/health`);
  return { status: res.status, body: await res.json() };
};

/**
 * POST to an /admin/* path with Bearer token authentication.
 *
 * @param {string} path - e.g. '/admin/index'
 * @param {Object} body
 * @param {Object} [opts]
 * @param {string} [opts.adminToken]
 * @returns {Promise<{status: number, body: Object}>}
 */
const adminPost = async (path, body, opts = {}) => {
  const token = opts.adminToken ?? adminToken;
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
};

/**
 * PUT to an /admin/* path with Bearer token authentication.
 * Used for config updates (PUT /admin/config).
 *
 * @param {string} path - e.g. '/admin/config'
 * @param {Object} body
 * @param {Object} [opts]
 * @param {string} [opts.adminToken]
 * @returns {Promise<{status: number, body: Object}>}
 */
const adminPut = async (path, body, opts = {}) => {
  const token = opts.adminToken ?? adminToken;
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
};

/**
 * GET an /admin/* path with Bearer token authentication.
 *
 * @param {string} path
 * @param {Object} [opts]
 * @param {string} [opts.adminToken]
 * @returns {Promise<{status: number, body: Object}>}
 */
const adminGet = async (path, opts = {}) => {
  const token = opts.adminToken ?? adminToken;
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  return { status: res.status, body: await res.json() };
};

/**
 * Raw POST with caller-supplied body string and headers.
 * Used for adversarial tests (malformed JSON, oversized bodies, header injection).
 * Returns the raw response body text, not parsed JSON.
 *
 * @param {string} path
 * @param {string} rawBody
 * @param {Object} [headers]
 * @returns {Promise<{status: number, body: string}>}
 */
const rawPost = async (path, rawBody, headers = {}) => {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: rawBody,
  });
  return { status: res.status, body: await res.text() };
};

module.exports = {
  BASE_URL,
  apiKey,
  adminToken,
  CREDS_OK,
  SKIP_REASON,
  query,
  queryBatch,
  suggest,
  health,
  adminPost,
  adminPut,
  adminGet,
  rawPost,
};
