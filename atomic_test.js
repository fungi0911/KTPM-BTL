/*
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 100,          // số lượng user ảo đồng thời
  duration: '20s',   // thời gian test
  thresholds: {
    http_req_failed: ['rate<0.01'],   // <1% lỗi
    http_req_duration: ['p(95)<500'], // 95% request <500ms
  },
};

// =============================
// ⚙️ Cấu hình
// =============================
const BASE_URL = 'http://127.0.0.1:8000';
const USERNAME = 'admin';
const PASSWORD = 'admin123';
const ITEM_ID = 1;

// =============================
// 🔐 Lấy JWT token và quantity ban đầu
// =============================
export function setup() {
  const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(loginRes, { 'login status 200': (r) => r.status === 200 });
  const token = loginRes.json('access_token');

  if (!token) {
    throw new Error(`Login failed: ${loginRes.body}`);
  }

  // Lấy quantity ban đầu
  const startRes = http.get(`${BASE_URL}/warehouse_items/${ITEM_ID}`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  const startQty = startRes.json('quantity');
  console.log(`🟢 Initial quantity: ${startQty}`);

  return { token, startQty };
}

// =============================
// 🚀 Mỗi VU sẽ gọi endpoint increment
// =============================
export default function (data) {
  if (!data || !data.token) {
    throw new Error('No data received from setup!');
  }

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.token}`,
  };

  const res = http.post(`${BASE_URL}/warehouse_items/${ITEM_ID}/increment`,
    JSON.stringify({ delta: 1 }),
    { headers }
  );

  check(res, { 'increment status 200': (r) => r.status === 200 });

  // Giữ rate ổn định, tránh spam quá nhanh
}

// =============================
// 📊 teardown() chạy sau khi test xong
// =============================
export function teardown(data) {
  if (!data || !data.token) {
    console.error('No data received from setup for teardown!');
    return;
  }

  const finalRes = http.get(`${BASE_URL}/warehouse_items/${ITEM_ID}`, {
    headers: { 'Authorization': `Bearer ${data.token}` },
  });

  const finalQty = finalRes.json('quantity');
  const delta = finalQty - data.startQty;

  console.log(`🔵 Final quantity: ${finalQty}`);
  console.log(`📈 Total incremented by: ${delta}`);
}
*/



import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 100,          // số lượng user ảo đồng thời
  duration: '20s',   // thời gian test
  thresholds: {
    http_req_failed: ['rate<0.01'],   // <1% lỗi
    http_req_duration: ['p(95)<500'], // 95% request <500ms
  },
};

// =============================
// ⚙️ Cấu hình
// =============================
const BASE_URL = 'http://127.0.0.1:8000';
const USERNAME = 'admin';
const PASSWORD = 'admin123';
// --- random list config ---
const RANDOM_COUNT = parseInt(__ENV.ITEM_RANDOM_COUNT || "1", 10);
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

// =============================
// 🔐 Lấy JWT token và quantity ban đầu
// =============================
export function setup() {
  console.log(`🟢 Selected random ids (${ITEM_IDS.length}): ${ITEM_IDS.join(',')}`);
  const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(loginRes, { 'login status 200': (r) => r.status === 200 });
  const token = loginRes.json('access_token');

  if (!token) {
    throw new Error(`Login failed: ${loginRes.body}`);
  }

  // Lấy quantity ban đầu cho nhiều id
  const startById = {};
  for (const id of ITEM_IDS) {
    const startRes = http.get(`${BASE_URL}/warehouse_items/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (startRes.status === 200) {
      startById[id] = startRes.json('quantity');
    } else {
      startById[id] = null; // không tồn tại / lỗi
    }
  }
  const startSum = Object.values(startById).reduce((a, b) => a + (b || 0), 0);
  console.log(`🟢 Initial quantities: ${JSON.stringify(startById)} | total=${startSum}`);

  return { token, itemIds: ITEM_IDS, startById };
}

// =============================
// 🚀 Mỗi VU sẽ gọi endpoint increment
// =============================
export default function (data) {
  if (!data || !data.token) {
    throw new Error('No data received from setup!');
  }
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.token}`,
  };
  // chọn ngẫu nhiên 1 id để increment
  const idx = Math.floor(Math.random() * data.itemIds.length);
  const id = data.itemIds[idx];

  const res = http.post(`${BASE_URL}/warehouse_items/${id}/increment`,
    JSON.stringify({ delta: 1 }),
    { headers }
  );
  check(res, { [`increment ${id} status 200`]: (r) => r.status === 200 });

  // Giữ rate ổn định, tránh spam quá nhanh
}

// =============================
// 📊 teardown() chạy sau khi test xong
// =============================
export function teardown(data) {
  if (!data || !data.token) {
    console.error('No data received from setup for teardown!');
    return;
  }

  const finalById = {};
  let finalSum = 0;
  for (const id of data.itemIds) {
    const finalRes = http.get(`${BASE_URL}/warehouse_items/${id}`, {
      headers: { 'Authorization': `Bearer ${data.token}` },
    });
    check(finalRes, { [`final ${id} status 200`]: (r) => r.status === 200 });
    const q = finalRes.json('quantity');
    finalById[id] = q;
    finalSum += (q || 0);
  }

  const startSum = Object.values(data.startById).reduce((a, b) => a + (b || 0), 0);
  console.log(`🔵 Final quantities: ${JSON.stringify(finalById)} | total=${finalSum}`);
  console.log(`📈 Total incremented by: ${finalSum - startSum}`);

  // In chi tiết từng id
  for (const id of data.itemIds) {
    const start = data.startById[id] ?? 0;
    const end = finalById[id] ?? start;
    console.log(`• id=${id}: start=${start}, final=${end}, delta=${end - start}`);
  }
}

// 1427634.22 ms