# Warehouse System – Technical Overview

Tài liệu mô tả toàn bộ kiến trúc, chiến lược tối ưu hóa và các kỹ thuật được áp dụng trong hệ thống Warehouse.

---

## 1. Caching

### 1.1. Chiến lược Caching
Hệ thống sử dụng mô hình **Cache-Aside (Lazy Loading)** để tối ưu hiệu năng đọc.

### 1.2. Luồng hoạt động

#### A. GET (Đọc dữ liệu)
1. Nhận request.
2. Kiểm tra Redis xem key có tồn tại không.
3. **Cache Hit** → Trả dữ liệu từ RAM.
4. **Cache Miss** → Query MySQL → Lưu vào Redis (TTL) → Trả kết quả.

#### B. Ghi dữ liệu (POST/PUT/DELETE)
1. Cập nhật MySQL.
2. **Xóa (invalidate)** các key liên quan trong Redis.
3. Lần đọc tiếp theo sẽ tự tạo cache mới.

---

## 2. Repository Pattern

**Mục tiêu:**
- Tăng khả năng tái sử dụng.
- Tách biệt rõ ràng business logic và data access.
- Dễ bảo trì và dễ test.
- Dễ thay đổi database (MySQL → PostgreSQL → MongoDB).

---

## 3. Nén dữ liệu

Sử dụng **Gzip** hoặc **Zstandard (zstd)** để nén JSON trước khi gửi đi, giúp:
- Giảm băng thông
- Giảm payload size
- Tăng tốc độ phản hồi

---

## 4. Hiệu năng thực tế

### 4.1. Trước khi có Cache (MySQL Only)
- Response time: **1.8s – 2.7s**
- Với ~30.000 records
- Toàn bộ request vào DB

### 4.2. Sau khi có Cache (Redis)
- Response time: **240ms – 300ms**
- Truy xuất từ RAM, không chạm DB

### So sánh

| Chỉ số        | MySQL Only | Redis Cache | Cải thiện |
|---------------|------------|-------------|-----------|
| Response Time | ~2.5 s     | ~250 ms     | ~10x      |
| DB Load       | 100%       | ~5%         | -95%      |

---

## 5. Circuit Breaker & Retry

### 5.1. Circuit Breaker
- Trạng thái: **Closed / Open / Half-Open**
- Ngắt request ngay khi dịch vụ đích lỗi
- Tránh quá tải dây chuyền

### 5.2. Retry (Tenacity)
- Exponential Backoff + Jitter
- Retry có điều kiện
- Ném lỗi `RetryExhaustedError` khi retry hết giới hạn

### 5.3. Mức độ dễ dùng
- Decorator: `@resilient_call`
- Config linh hoạt: fail_max, timeout, backoff, exclude_exceptions

---

## 6. Database & Backend Optimization

### 6.1. Chuyển từ SQLite → MySQL
Lý do:
- SQLite khóa file → nghẽn khi concurrent
- MySQL hỗ trợ nhiều kết nối, row-level lock
- Mở rộng tốt hơn, ổn định hơn

### 6.2. Optimistic Concurrency Control (OCC)
Giải quyết **lost update**.

**Luồng thực hiện:**
1. Client gửi dữ liệu + version hiện tại.
2. `UPDATE ... WHERE version = client_version`
3. Nếu version khớp → cập nhật + tăng version
4. Nếu không → báo lỗi để client xử lý

---

## 7. Rate Limit & Queue-based Load Leveling

### 7.1. Rate Limit
- Giảm spam, tránh DoS nhẹ
- Giới hạn request theo IP
- Dùng **Flask-Limiter**

### 7.2. Queue-based Load Leveling
Áp dụng cho tác vụ nặng:  
(Celery + Redis Queue)

**Luồng xử lý:**
1. Client gửi request
2. API đẩy task vào queue, trả về `task_id`
3. Worker xử lý
4. Client kiểm tra trạng thái qua `/task/<task_id>`
5. Khi hoàn tất → trả kết quả

---

## Tổng kết

| Thành phần | Công nghệ |
|-----------|-----------|
| Cache | Redis Cache-Aside |
| DB Access | Repository Pattern |
| Compression | Gzip / Zstd |
| Concurrency Control | OCC |
| Resilience | Circuit Breaker, Retry |
| Backend Server | Gunicorn |
| Rate Limit | Flask-Limiter |
| Load Leveling | Celery + Redis |
| Database | MySQL |

Hệ thống đạt được:
- **Nhanh hơn ~10 lần**
- **Giảm ~95% tải DB**
- **ổn định, mở rộng dễ dàng**
- **chống race condition và mất dữ liệu**
- **không nghẽn request nặng**

---
