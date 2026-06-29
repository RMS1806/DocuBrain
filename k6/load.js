/**
 * k6/load.js — Load test
 *
 * Purpose: measure steady-state performance under realistic concurrent load.
 * Find the P95/P99 latency profile and verify the system stays stable for
 * several minutes — not just a burst.
 *
 * Shape (stages):
 *
 *   VUs
 *   50 |          ┌─────────────────────┐
 *      |         /│                     │\
 *      |        / │                     │ \
 *    5 |───────/  │                     │  \────
 *      |      /   │                     │
 *      0  30s  1m30s                  4m30s  5m
 *         ramp   ←── steady state ──→   ramp
 *                       (3 minutes)      down
 *
 * Thresholds (pass/fail gates):
 *   P95 < 500ms  — 95% of requests under half a second
 *   P99 < 1000ms — worst 1% stays under 1 second
 *   error rate < 1%
 *
 * Custom metrics show WHERE time is being spent — is it auth? DB queries? Nginx?
 *
 * Run locally:
 *   k6 run --env BASE_URL=http://localhost k6/load.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { BASE_URL, register, login, authHeaders } from './helpers.js';

// ── Custom metrics ─────────────────────────────────────────────────────────────
// k6's built-in http_req_duration tracks ALL requests together.
// Custom Trend metrics let you track specific endpoint latencies separately.
// In the final report, you see: "analytics_duration p95=320ms" vs "docs_duration p95=45ms"
// This immediately tells you WHICH endpoint is the bottleneck.

// Trend: tracks a distribution of values (min, max, avg, p50, p90, p95, p99)
const docsLatency      = new Trend('docs_duration',      true); // true = display in ms
const analyticsLatency = new Trend('analytics_duration', true);
const progressLatency  = new Trend('progress_duration',  true);

// Rate: tracks a proportion (value between 0 and 1) — e.g. error rate per endpoint
const docsErrorRate = new Rate('docs_errors');

// Counter: tracks a running total — e.g. how many 429s did we get?
const rateLimitHits = new Counter('rate_limit_429s');

// ── VU-local state ─────────────────────────────────────────────────────────────
// Each VU gets its own JS runtime in k6, so this Map is per-VU (not shared).
// We use it to register + login once on the first iteration, then reuse the token.
const vuState = new Map();


export const options = {
  // stages: the "shape" of the load over time.
  // Each stage ramps VUs linearly from the current count to `target`.
  stages: [
    // Start at 0 (default), ramp to 5 over 30s — let the server warm up.
    // Cold start: JIT compilation, connection pool filling, cache warming.
    // Without a warm-up stage, the first requests are slower and skew your P99.
    { duration: '30s', target: 5  },

    // Ramp from 5 to 50 over 1 minute — gradual climb to find where latency
    // starts degrading. If P95 jumps at 30 VUs, your bottleneck is there.
    { duration: '1m',  target: 50 },

    // Hold at 50 VUs for 3 minutes — the main measurement window.
    // 3 minutes gives enough samples for statistically meaningful percentiles.
    // (A P99 from 10 requests is meaningless; from 1000 requests it's real.)
    { duration: '3m',  target: 50 },

    // Ramp down — verify the server recovers cleanly.
    // If latency stays high after VUs drop, you have a resource leak
    // (e.g. DB connections not being returned to the pool).
    { duration: '30s', target: 0  },
  ],

  thresholds: {
    // Built-in metric: covers all requests
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'http_req_failed':   ['rate<0.01'],

    // Custom per-endpoint thresholds
    'docs_duration':      ['p(95)<200'],  // listing docs should be fast (cached + simple query)
    'analytics_duration': ['p(95)<600'],  // analytics has 5 aggregate SQL queries
    'progress_duration':  ['p(95)<400'],

    // Document error rate (4xx/5xx from /documents/)
    'docs_errors': ['rate<0.05'],
  },
};


// setup() runs once before any VU starts.
// Each VU self-registers on its own first iteration using its unique __VU id,
// so setup() has nothing to do here.
export function setup() {
  return {};
}


export default function () {
  // Each VU registers and logs in on its very first iteration (__ITER === 0).
  // On subsequent iterations it reuses the token stored in this VU's Map entry.
  //
  // register() generates a unique email per VU: loadtest-vu{N}-iter0@example.com
  // so 50 VUs = 50 independent user accounts — no shared state, no conflicts.
  if (!vuState.has(__VU)) {
    const creds = register();
    const token = login(creds);
    vuState.set(__VU, { headers: authHeaders(token) });
  }
  const { headers } = vuState.get(__VU);

  // ── Scenario: a user opening the dashboard ─────────────────────────────────

  // 1. Document list
  const docsStart = Date.now();
  const docs = http.get(`${BASE_URL}/documents/`, { headers });
  docsLatency.add(Date.now() - docsStart);
  docsErrorRate.add(docs.status >= 400);
  if (docs.status === 429) rateLimitHits.add(1);
  check(docs, { 'docs: 200': (r) => r.status === 200 });

  sleep(randomBetween(0.5, 1.5));   // user reads the document list

  // 2. Analytics dashboard — the most expensive read (5 aggregate SQL queries)
  const analyticsStart = Date.now();
  const analytics = http.get(`${BASE_URL}/analytics/dashboard`, { headers });
  analyticsLatency.add(Date.now() - analyticsStart);
  check(analytics, { 'analytics: 200': (r) => r.status === 200 });

  sleep(randomBetween(1, 3));       // user reads the dashboard

  // 3. Progress stats
  const progressStart = Date.now();
  const progress = http.get(`${BASE_URL}/progress/stats`, { headers });
  progressLatency.add(Date.now() - progressStart);
  check(progress, { 'progress: 200': (r) => r.status === 200 });

  sleep(randomBetween(0.5, 2));
}


// ── Utility ────────────────────────────────────────────────────────────────────
// Random sleep duration between min and max seconds — simulates realistic
// think time. Real users don't all pause for exactly 1.000 second.
function randomBetween(min, max) {
  return Math.random() * (max - min) + min;
}
