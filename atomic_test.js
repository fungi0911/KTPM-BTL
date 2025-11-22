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
