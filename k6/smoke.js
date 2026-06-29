/**
 * k6/smoke.js — Smoke test
 *
 * Purpose: confirm the app is alive and every core endpoint responds correctly
 * under zero load stress. This runs automatically in CI after every deploy.
 *
 * Shape:
 *   1 virtual user
 *   30 seconds
 *   P95 latency must be under 300ms (tighter than load test — no excuse at 1 VU)
 *   Error rate must be exactly 0%
 *
 * If this fails, the deploy is broken outright. A smoke test failure means
 * something is fundamentally wrong — migrations didn't run, a service is down,
 * env vars are missing — not just "the server is slow under pressure".
 *
 * Run locally:
 *   k6 run --env BASE_URL=http://localhost k6/smoke.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, setupUser } from './helpers.js';

export const options = {
  vus: 1,
  duration: '30s',

  // Thresholds are PASS/FAIL gates — k6 exits with code 1 if any breach.
  // In CI, exit code 1 fails the job. This is what makes load tests a quality gate.
  thresholds: {
    // http_req_duration tracks every HTTP request made in the test.
    // p(95) = the 95th percentile — 95% of requests must be under this value.
    // At 1 VU with no contention, 300ms is generous — most should be under 50ms.
    'http_req_duration': ['p(95)<300'],

    // http_req_failed is a built-in rate metric: (failed requests / total requests).
    // A request is "failed" if it gets a network error OR a 4xx/5xx status.
    // rate=0 means: zero tolerance for errors in the smoke test.
    'http_req_failed': ['rate==0'],
  },
};


// setup() runs ONCE before the main VU loop starts.
// Use it for expensive one-time operations: registering a user, seeding data.
// The return value is passed to the default function as `data`.
//
// Why not register inside default()? Because default() runs on every iteration.
// If our test runs for 30s with 1 iteration/second, we'd register 30 users.
// Instead, we register once and reuse the token for all iterations.
export function setup() {
  const result = setupUser();
  console.log(`setup: token=${result.token ? result.token.substring(0, 20) + '...' : 'NULL'}`);
  return result;
}


// default() is the VU lifecycle — called repeatedly until the duration ends.
// Each call = one "iteration". k6 tracks iterations/second as throughput.
export default function ({ headers }) {
  // ── 1. Health check ────────────────────────────────────────────────────────
  // Always test /health first. If this fails, every other failure is noise —
  // the server is simply down. Testing /health separately gives you a clear
  // signal in the report: "health check failed" vs "auth failed".
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    'health: status 200': (r) => r.status === 200,
    'health: body has status ok': (r) => r.json('status') === 'ok',
  });

  // ── 2. Document list ────────────────────────────────────────────────────────
  const docs = http.get(`${BASE_URL}/documents/`, { headers });
  check(docs, {
    'documents: status 200': (r) => r.status === 200,
    'documents: returns array': (r) => Array.isArray(r.json()),
  });

  // ── 3. Analytics dashboard ─────────────────────────────────────────────────
  // This exercises the read replica path (get_read_db) and asyncio.gather
  // with 5 concurrent SQL queries — the most complex read endpoint.
  const analytics = http.get(`${BASE_URL}/analytics/dashboard`, { headers });
  check(analytics, {
    'analytics: status 200': (r) => r.status === 200,
    'analytics: has documents_uploaded': (r) => r.json('documents_uploaded') !== undefined,
    'analytics: has quizzes_generated':  (r) => r.json('quizzes_generated')  !== undefined,
  });

  // ── 4. Progress stats ───────────────────────────────────────────────────────
  const progress = http.get(`${BASE_URL}/progress/stats`, { headers });
  check(progress, {
    'progress: status 200': (r) => r.status === 200,
  });

  // ── 5. /metrics must be blocked ────────────────────────────────────────────
  // In production (with Nginx), this returns 403.
  // This check verifies the Nginx config is active — if /metrics returns 200,
  // it means requests are bypassing Nginx and hitting FastAPI directly.
  // 403 is expected here — http.setResponseCallback in helpers.js excludes it from http_req_failed.
  const metrics = http.get(`${BASE_URL}/metrics`);
  check(metrics, {
    'metrics: blocked by Nginx (403)': (r) => r.status === 403,
  });

  // Think time: pause between iterations to simulate a human reading a page.
  // Without this, the VU fires requests as fast as the server responds —
  // unrealistically aggressive even for a smoke test.
  sleep(1);
}
