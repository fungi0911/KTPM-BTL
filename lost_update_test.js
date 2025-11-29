import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: parseInt(__ENV.VUS || '100', 10),
  duration: __ENV.DURATION || '20s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const USERNAME = __ENV.USERNAME || 'admin';
const PASSWORD = __ENV.PASSWORD || 'admin123';
const RANDOM_COUNT = parseInt(__ENV.ITEM_RANDOM_COUNT || '1', 10);
const RANDOM_MAX_ID = parseInt(__ENV.ITEM_RANDOM_MAX_ID || '30000', 10);

function randomUniqueIds(count, maxId) {
  const pool = new Set();
  while (pool.size < count) {
    const v = Math.floor(Math.random() * maxId) + 1;
    pool.add(v);
  }
  return Array.from(pool);
}
const ITEM_IDS = randomUniqueIds(RANDOM_COUNT, RANDOM_MAX_ID);

export function setup() {
  const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  check(loginRes, { 'login 200': (r) => r.status === 200 });
  const token = loginRes.json('access_token');
  if (!token) { throw new Error(`Login failed: ${loginRes.body}`); }

  const startById = {};
  for (const id of ITEM_IDS) {
    const res = http.get(`${BASE_URL}/warehouse_items/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    startById[id] = res.status === 200 ? res.json('quantity') : null;
  }
  return { token, itemIds: ITEM_IDS, startById };
}

export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.token}`,
  };
  const idx = Math.floor(Math.random() * data.itemIds.length);
  const id = data.itemIds[idx];

  // Read-modify-write via PUT: simulate potential lost update
  const getRes = http.get(`${BASE_URL}/warehouse_items/${id}`, { headers });
  if (getRes.status !== 200) { return; }
  const currentQty = getRes.json('quantity') || 0;
  const newQty = currentQty + 1;

  const putRes = http.put(`${BASE_URL}/warehouse_items/${id}`, JSON.stringify({ quantity: newQty }), { headers });
  check(putRes, { [`put ${id} 200`]: (r) => r.status === 200 || r.status === 409 });
}

export function teardown(data) {
  const headers = { 'Authorization': `Bearer ${data.token}` };
  const finalById = {};
  let finalSum = 0;
  for (const id of data.itemIds) {
    const res = http.get(`${BASE_URL}/warehouse_items/${id}`, { headers });
    const q = res.status === 200 ? res.json('quantity') : 0;
    finalById[id] = q;
    finalSum += q;
  }
  const startSum = Object.values(data.startById).reduce((a, b) => a + (b || 0), 0);
  console.log(`Final quantities: ${JSON.stringify(finalById)} | total=${finalSum}`);
  console.log(`Total delta: ${finalSum - startSum}`);
}
