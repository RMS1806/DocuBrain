/**
 * k6/helpers.js — shared utilities imported by every test script.
 *
 * k6 uses its own JavaScript runtime (goja — a Go-based JS engine), NOT Node.js.
 * This means:
 *   - No require() — use ES module imports (import/export)
 *   - No npm packages — only k6's built-in modules (k6/http, k6/metrics, etc.)
 *   - __ENV.VAR_NAME reads environment variables passed via --env flag
 *   - Math.random() works, but Date and setTimeout behave differently
 *
 * BASE_URL is read from the --env flag so the same scripts work against
 * local dev, staging, and production without code changes:
 *   k6 run --env BASE_URL=http://localhost smoke.js
 *   k6 run --env BASE_URL=https://api.docubrain.com load.js
 */

import http from 'k6/http';
import { check } from 'k6';

export const BASE_URL = __ENV.BASE_URL || 'http://localhost';

// JSON content-type header — used on every POST request
const JSON_HEADERS = { 'Content-Type': 'application/json' };

// Override the default "any 4xx/5xx = failed" rule globally.
// 400: setupUser register returns "Email already registered" on re-runs — expected.
// 403: Nginx blocks /metrics — that IS the correct behaviour.
// Without this, http_req_failed counts these intentional non-2xx responses as errors.
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 399 }, 400, 403));


/**
 * Register a new user account and return their credentials.
 *
 * Each VU (virtual user) must have a unique email — if two VUs try to
 * register the same email, one gets a 409 Conflict, which would be counted
 * as an error and skew your results.
 *
 * We use a combination of VU ID (__VU) and iteration count (__ITER) to
 * guarantee uniqueness across all concurrent users and all test iterations.
 *   __VU   = which virtual user (1, 2, 3 ... up to your max VUs)
 *   __ITER = how many times this VU has run the default function (0, 1, 2 ...)
 *
 * So VU 5 on its 3rd iteration gets email: loadtest-vu5-iter3@example.com
 */
export function register() {
  // __VU and __ITER are only defined inside the default() VU loop.
  // setup() runs before any VU starts, so both are undefined there.
  // We fall back to a timestamp suffix so setup() gets a unique email too.
  const vu   = typeof __VU   !== 'undefined' ? __VU   : 0;
  const iter = typeof __ITER !== 'undefined' ? __ITER : Date.now();
  const email = `loadtest-vu${vu}-iter${iter}@example.com`;
  const payload = JSON.stringify({
    email,
    password: 'LoadTest1234!',
    full_name: 'Load Test User',
  });

  const res = http.post(`${BASE_URL}/auth/register`, payload, {
    headers: JSON_HEADERS,
  });

  // check(): k6's assertion function. Unlike a throw, a failed check does NOT
  // stop the VU — it marks the check as failed and increments the error counter.
  // This is intentional: we want to keep measuring even when some requests fail,
  // to see the ERROR RATE under load, not just whether one request worked.
  check(res, {
    'register: status is 200': (r) => r.status === 200,
  });

  return { email, password: 'LoadTest1234!' };
}


/**
 * Log in and return the JWT access token string.
 * The token is used for all subsequent authenticated requests in that VU's session.
 */
export function login(credentials) {
  // FastAPI's OAuth2PasswordRequestForm expects form-encoded data, not JSON.
  // The field name is "username" (OAuth2 spec), not "email".
  const res = http.post(
    `${BASE_URL}/auth/login`,
    `username=${encodeURIComponent(credentials.email)}&password=${encodeURIComponent(credentials.password)}`,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
  );

  check(res, {
    'login: status is 200': (r) => r.status === 200,
    'login: has access_token': (r) => r.json('access_token') !== undefined,
  });

  return res.json('access_token');
}


/**
 * Build the HTTP headers object for an authenticated request.
 * Pass the result directly to any http.get / http.post call as the headers option.
 */
export function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };
}


/**
 * Create (or reuse) a fixed test user and return a valid token.
 *
 * Uses a fixed email so setup() works across multiple test runs:
 *   - First run:  register returns 200 → user created
 *   - Later runs: register returns 409 → user already exists (fine, we ignore it)
 *   - Always:     login with fixed credentials → valid token
 *
 * Do NOT use register() here — that generates a unique email per VU+iter,
 * which is correct for load tests but wrong for setup() where __ITER is always 0.
 */
export function setupUser() {
  const email    = 'loadtest-setup@example.com';
  const password = 'LoadTest1234!';

  // Register — 200 (new user) or 409 (already exists) are both acceptable.
  http.post(
    `${BASE_URL}/auth/register`,
    JSON.stringify({ email, password, full_name: 'Load Test User' }),
    { headers: { 'Content-Type': 'application/json' } },
  );

  // Always login — works whether the user was just created or already existed.
  const token = login({ email, password });
  return { token, headers: authHeaders(token) };
}
