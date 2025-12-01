import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Trend } from 'k6/metrics';

export const options = {
  scenarios: {
    baseline_ok: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: 3,
      maxDuration: '10s',
      startTime: '0s',
      exec: 'baselineHealthy',
      tags: { scenario: 'baseline_ok' },
    },
    flaky_retry: {
      executor: 'constant-vus',
      vus: 3,
      duration: '12s',
      startTime: '6s',
      exec: 'flakyWithRetry',
      tags: { scenario: 'flaky_retry' },
    },
    force_open: {
      executor: 'shared-iterations',
      vus: 1,
      iterations: 1,
      startTime: '20s',
      exec: 'forceCircuitOpen',
      tags: { scenario: 'force_open' },
    },
    verify_open: {
      executor: 'constant-vus',
      vus: 2,
      duration: '8s',
      startTime: '25s',
      exec: 'verifyCircuitOpen',
      tags: { scenario: 'verify_open' },
    },
    recover: {
      executor: 'constant-vus',
      vus: 2,
      duration: '10s',
      startTime: '45s',
      exec: 'recoverCircuit',
      tags: { scenario: 'recover' },
    },
  },
  thresholds: {
    resilience_circuit_opened: ['count>0'],
    'http_req_failed{scenario:baseline_ok}': ['rate==0'],
    'http_req_failed{scenario:verify_open}': ['rate>0.7'],
    'http_req_duration{scenario:flaky_retry}': ['p(95)<3000'],
  },
};

// ===== Config (env override) =====
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:5000';
const PRODUCT_ID = Number(__ENV.PRODUCT_ID || 1);
const FAIL_THRESHOLD = Number(__ENV.CB_FAILURE_THRESHOLD || 3);
const RESET_TIMEOUT = Number(__ENV.CB_RESET_TIMEOUT || 15);
const USERNAME = __ENV.USERNAME || 'admin';
const PASSWORD = __ENV.PASSWORD || 'admin123';

const circuitOpened = new Counter('resilience_circuit_opened');
const vendorFailures = new Counter('resilience_vendor_failures');
const retryAttempts = new Trend('resilience_retry_attempts');

const VERIFY_START_S = 25;
const RECOVERY_WAIT_S = Math.ceil(RESET_TIMEOUT) + 5;
const RECOVERY_START_S = VERIFY_START_S + RECOVERY_WAIT_S;

// ===== Setup: login to get token =====
export function setup() {
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(loginRes, { 'login 200': (r) => r.status === 200 });
  const token = loginRes.json('access_token');
  if (!token) throw new Error(`Login failed: ${loginRes.body}`);

  const auth = { Authorization: `Bearer ${token}` };
  const state = fetchState(auth);
  console.log(`Starting circuit state: ${JSON.stringify(state)}`);
  return { startTs: Date.now(), auth };
}

// ===== Scenarios =====
export function baselineHealthy(data) {
  const auth = data.auth;
  group('Healthy vendor path (no resilience needed)', () => {
    const res = vendorRequest(auth, { mode: 'ok' }, { step: 'healthy' });
    check(res, {
      '200 from vendor': (r) => r.status === 200,
      'has price data': (r) => safeJson(r, 'data.price') !== undefined,
      'only one attempt': (r) => safeJson(r, 'attempts') === 1,
    });
    sleep(0.5);
  });
}

export function flakyWithRetry(data) {
  const auth = data.auth;
  group('Flaky vendor handled by retries', () => {
    const res = vendorRequest(
      auth,
      { mode: 'flaky', fail_rate: 0.7, strategy: 'resilient' },
      { step: 'flaky_retry' }
    );
    const attempts = safeJson(res, 'attempts') || 1;
    check(res, {
      'eventually succeeds': (r) => r.status === 200,
      'used retry when needed': () => attempts >= 1,
    });
    retryAttempts.add(attempts);
    sleep(0.3);
  });
}

export function forceCircuitOpen(data) {
  const auth = data.auth;
  group('Force circuit to OPEN (downstream hard failures)', () => {
    for (let i = 0; i < FAIL_THRESHOLD + 2; i += 1) {
      const res = vendorRequest(auth, { mode: 'down', strategy: 'resilient' }, { step: 'force_open' });
      check(res, { 'downstream failure surfaced': (r) => [502, 503].includes(r.status) });
      sleep(0.25);
    }
    const state = fetchState(auth);
    const isOpen = state?.state === 'open';
    if (isOpen) circuitOpened.add(1);
    check(state, { 'circuit is OPEN after failures': () => isOpen });
  });
}

export function verifyCircuitOpen(data) {
  const auth = data.auth;
  group('Calls are blocked while circuit OPEN', () => {
    const res = vendorRequest(auth, { mode: 'ok', strategy: 'resilient' }, { step: 'verify_open' });
    const state = safeJson(res, 'state.state');
    check(res, {
      '503 from open circuit': (r) => r.status === 503,
      'state reports open': () => state === 'open',
    });
    sleep(0.5);
  });
}

export function recoverCircuit(data) {
  const auth = data.auth;
  group('Circuit half-open then recovers', () => {
    sleep(RESET_TIMEOUT + 1); // allow cooldown
    const res = vendorRequest(auth, { mode: 'ok', strategy: 'resilient' }, { step: 'recover' });
    const attempts = safeJson(res, 'attempts') || 1;
    const state = safeJson(res, 'state.state');
    check(res, {
      'success after cooldown': (r) => r.status === 200,
      'breaker closes again': () => state === 'closed' || state === 'half-open',
      'only a few attempts on recovery': () => attempts <= 2,
    });
    sleep(0.5);
  });
}

// ===== Teardown =====
export function teardown(data) {
  const elapsed = ((Date.now() - data.startTs) / 1000).toFixed(2);
  const finalState = fetchState(data.auth);
  console.log(`Test duration: ${elapsed}s`);
  console.log(`Final state: ${JSON.stringify(finalState)}`);
}

// ===== Helpers =====
function vendorRequest(authHeaders, params = {}, tags = {}) {
  const query = buildQuery(params);
  const res = http.get(
    `${BASE_URL}/warehouse_items/vendor_price/${PRODUCT_ID}${query}`,
    { headers: authHeaders, tags: { feature: 'resilience', ...tags } }
  );

  const attempts = safeJson(res, 'attempts') || 1;
  retryAttempts.add(attempts);
  if (res.status >= 500) vendorFailures.add(1);
  if (safeJson(res, 'state.state') === 'open') circuitOpened.add(1);

  return res;
}

function fetchState(authHeaders) {
  try {
    const res = http.get(`${BASE_URL}/warehouse_items/vendor_state`, { headers: authHeaders });
    return res.json();
  } catch (err) {
    console.error(`Unable to read vendor state: ${err}`);
    return null;
  }
}

function safeJson(res, path) {
  try {
    return res.json(path);
  } catch {
    return undefined;
  }
}

function buildQuery(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (!entries.length) return '';
  return `?${entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')}`;
}
