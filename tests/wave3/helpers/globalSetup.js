'use strict';

/**
 * Jest globalSetup — runs once before all test suites.
 *
 * Pings /health to absorb the Lambda cold start (ONNX model load can take
 * 20-30 s on the first invocation). Without this, the first test in each
 * parallel worker times out.
 */

const fetch = require('node-fetch');

module.exports = async function globalSetup() {
  const BASE_URL =
    process.env.NAV_API_URL ||
    'https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com';

  const WARMUP_TIMEOUT_MS = 40_000;
  const start = Date.now();

  process.stdout.write('\n[wave3 setup] warming up Lambda cold start… ');
  try {
    const res = await fetch(`${BASE_URL}/health`, { timeout: WARMUP_TIMEOUT_MS });
    const elapsed = Date.now() - start;
    process.stdout.write(`done (${res.status}, ${elapsed}ms)\n`);
  } catch (err) {
    const elapsed = Date.now() - start;
    process.stdout.write(`warning: warmup failed after ${elapsed}ms — ${err.message}\n`);
    // Do not throw: if /health is unreachable the individual tests will fail
    // with meaningful errors rather than a cryptic setup failure.
  }
};
