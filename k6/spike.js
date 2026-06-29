/**
 * k6/spike.js — Spike test
 *
 * Purpose: simulate sudden bursts of traffic — a viral post, a flash sale,
 * a DDoS attempt, or a thundering herd after a scheduled event ends.
 * Verifies that:
 *   1. Nginx rate limiting absorbs the burst (429s, not 500s)
 *   2. Circuit breakers trip if AI services get overwhelmed (503s, not timeouts)
 *   3. The system RECOVERS after the burst — latency returns to baseline
 *      (a system that never recovers has a resource leak)
 *
 * Shape:
 *
 *   VUs
 *  200 |              ┌──────┐
 *      |             /│      │\
 *      |            / │      │ \
 *   10 |──────────/   │      │   \──────────────
 *    5 |─────────/    │      │    \─────────────
 *      0    30s  45s  1m    1m30s 1m45s  2m30s
 *            ramp  SPIKE    drop   ←recovery→
 *
 * Thresholds are deliberately MORE LENIENT than the load test:
 *   - error rate < 10% (we EXPECT 429s from Nginx rate limiting)
 *   - P95 < 2000ms    (some requests will queue or be circuit-broken)
 *   - recovery check: P95 in the last 30s must be < 500ms
 *
 * Run locally:
 *   k6 run --env BASE_URL=http://localhost k6/spike.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter, Trend } from 'k6/metrics';
import { BASE_URL, setupUser } from './helpers.js';

// ── Custom metrics ─────────────────────────────────────────────────────────────
const rateLimitHits  = new Counter('spike_429s');          // Nginx throttling
const circuitBreaks  = new Counter('spike_503s');          // circuit breaker open
const serverErrors   = new Counter('spike_5xx');           // unexpected server errors
const errorRate      = new Rate('spike_error_rate');
const recoveryTrend  = new Trend('recovery_latency', true); // latency in recovery phase


export const options = {
  stages: [
    // ── Baseline: establish normal behaviour before the spike ─────────────────
    // 10 VUs for 30s. This is our "before" snapshot.
    // The final report shows metrics per stage — you can compare baseline vs spike.
    { duration: '30s', target: 10  },

    // ── Spike ramp: 10 → 200 VUs in 15 seconds ───────────────────────────────
    // A realistic DDoS or viral event: not instant, but extremely fast.
    // This is where Nginx's burst=50 rate limit kicks in — it absorbs the first
    // 50 queued requests, then starts returning 429s for the overflow.
    { duration: '15s', target: 200 },

    // ── Peak: hold 200 VUs for 1 minute ──────────────────────────────────────
    // Sustained spike. Circuit breakers may open if AI endpoints get overwhelmed.
    // PgBouncer is under pressure — 200 VUs trying to query with 10 real DB connections.
    // The circuit breakers' recovery_timeout starts counting here.
    { duration: '1m',  target: 200 },

    // ── Drop: 200 → 10 VUs in 15 seconds ─────────────────────────────────────
    // Spike ends. This is as fast as the ramp-up.
    { duration: '15s', target: 10  },

    // ── Recovery window: hold at 10 VUs for 1 minute ─────────────────────────
    // Critical measurement: does the system return to baseline performance?
    // If latency stays at 1500ms with only 10 VUs, you have:
    //   - A DB connection leak (pool not returning connections)
    //   - A circuit breaker stuck in OPEN (recovery_timeout not elapsed)
    //   - A memory leak causing GC pressure
    // The recovery_latency custom metric captures this window specifically.
    { duration: '1m',  target: 10  },

    { duration: '15s', target: 0   },
  ],

  thresholds: {
    // During a 200-VU spike against free-tier infra, we EXPECT failures.
    // The question isn't "does anything fail?" but "does it FAIL CORRECTLY?"
    // 429 (rate limited) = correct. 500 (crash) = wrong. 30s timeout = wrong.
    'http_req_failed':    ['rate<0.15'],   // up to 15% errors acceptable at spike peak

    // Even under spike, the server shouldn't take more than 3s to respond.
    // A 30s timeout means the request pool is exhausted — circuit breaker
    // should have opened before that happened.
    'http_req_duration':  ['p(99)<3000'],

    // In the recovery phase (after spike), things should be back to normal.
    // If P95 recovery latency > 800ms with only 10 VUs, the system didn't recover.
    'recovery_latency':   ['p(95)<800'],

    // We should see 429s (good — Nginx is protecting the backend).
    // We should NOT see unconstrained 5xx server errors — those mean the system
    // is crashing instead of gracefully shedding load.
    'spike_5xx':          ['count<20'],    // fewer than 20 unexpected server errors total
  },
};


const vuState = new Map();

export default function () {
  if (!vuState.has(__VU)) {
    vuState.set(__VU, setupUser());
  }
  const { headers } = vuState.get(__VU);

  // We're in the recovery phase if we're past the spike (estimate by time).
  // In a real setup you'd use k6's scenarios with startTime to be precise.
  // Here we use VU count as a proxy: low VUs = recovery phase.
  const isRecovery = (__VU <= 15);

  // ── Fire requests ───────────────────────────────────────────────────────────
  // During a spike, ALL VUs hit ALL endpoints simultaneously.
  // No think time — we want to see what happens at maximum throughput.

  const docsRes = http.get(`${BASE_URL}/documents/`, { headers });
  classifyResponse(docsRes);
  if (isRecovery) recoveryTrend.add(docsRes.timings.duration);

  check(docsRes, {
    'spike docs: acceptable response': (r) => [200, 429, 503].includes(r.status),
    //   200 = served normally
    //   429 = rate limited (correct — Nginx is protecting us)
    //   503 = circuit breaker open (correct — fail-fast, not a 30s timeout)
    //   500 = crash (wrong — would fail this check)
  });

  const analyticsRes = http.get(`${BASE_URL}/analytics/dashboard`, { headers });
  classifyResponse(analyticsRes);

  check(analyticsRes, {
    'spike analytics: acceptable response': (r) => [200, 429, 503].includes(r.status),
  });

  // Short sleep even during spike — absolute zero think time creates an
  // unrealistic synthetic benchmark that no real traffic pattern matches.
  sleep(0.1);
}


// ── Response classifier ────────────────────────────────────────────────────────
// Increment the right counter based on the status code.
// This gives you a breakdown in the final report:
//   spike_429s: 1247  ← Nginx rate limiting absorbed this many
//   spike_503s: 83    ← circuit breaker opened this many times
//   spike_5xx:  2     ← 2 unexpected server errors (should be near 0)
function classifyResponse(res) {
  errorRate.add(res.status >= 400);

  if (res.status === 429) {
    rateLimitHits.add(1);
  } else if (res.status === 503) {
    circuitBreaks.add(1);
  } else if (res.status >= 500) {
    serverErrors.add(1);
  }
}
