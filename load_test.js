import http from "k6/http";
import { check, sleep } from "k6";

// 1. Cấu hình kịch bản chạy
export const options = {
    // Giả lập 50 người dùng ảo (Virtual Users) truy cập cùng lúc
    vus: 50,
    // Chạy liên tục trong 30 giây
    duration: "30s",

    // (Tùy chọn) Ngưỡng chấp nhận được: 95% request phải nhanh hơn 200ms
    thresholds: {
        http_req_duration: ["p(95)<2000"],
    },
};

// 2. Hàm giả lập hành động của 1 người dùng
export default function () {
    // Thay URL API của bạn vào đây
    const url = "http://127.0.0.1:5000/warehouse_items";

    // Thay Token thật lấy từ Postman/Login vào đây
    const token =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDU3NDAxNiwianRpIjoiMWIzNDRlNDMtYzE5Ny00YjgyLTg4NmQtZjQ5Y2MzZjUxYjVmIiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzY0NTc0MDE2LCJjc3JmIjoiMWRhZDcxYmUtZWVjMi00NDg4LTlkMGItOTI5ODFkYzAyZjc4IiwiZXhwIjoxNzY0NTgxMjE2LCJyb2xlIjoiYWRtaW4ifQ.4HfhJYVSlJAbrn--4JTN8P4CFbWYxks_Eru5vQF9nFk";

    const params = {
        headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        },
    };

    // Gửi request GET
    const res = http.get(url, params);

    // Kiểm tra xem API có trả về 200 OK không
    check(res, {
        "status is 200": (r) => r.status === 200,
    });

    // Nghỉ 0.1 giây rồi spam tiếp (mô phỏng người dùng click rất nhanh)
    sleep(0.1);
}
