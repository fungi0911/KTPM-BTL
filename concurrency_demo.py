import concurrent.futures
import time
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"




def login(username="admin", password="admin123"):
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password
    }, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]

def get_item(item_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/warehouse_items/{item_id}", headers=headers, timeout=5)
    r.raise_for_status()
    return r.json()


def increment_once(token, item_id, delta=1, mode=None):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/warehouse_items/{item_id}/increment"
    if mode == "naive":
        url += "?mode=naive"
    r = requests.post(url, json={"delta": delta}, headers=headers, timeout=5)
    return r.status_code


def run_phase(name, token, item_id, count, mode=None):
    t0 = time.time()
    statuses = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(increment_once, token, item_id, 1, mode) for _ in range(count)]
        for fut in concurrent.futures.as_completed(futures):
            statuses.append(fut.result())
    dt = time.time() - t0
    print(f"{name}: {count} requests in {dt:.2f}s, status 200={statuses.count(200)}, status 409={statuses.count(409)}")
    return statuses


def main():
    print("Concurrency demo: naive vs OCC")
    token = login()

    item_id = 5

    q0 = get_item(item_id, token)["quantity"]
    print(f"Initial quantity: {q0}")

    count = 200
    run_phase("Naive", token, item_id, count, mode="naive")
    q1 = get_item(item_id, token)["quantity"]
    print(f"After naive: {q1} (expected {q0 + count} if no lost updates)")

    headers = {"Authorization": f"Bearer {token}"}
    requests.put(f"{BASE_URL}/warehouse_items/{item_id}", json={"quantity": 0}, headers=headers, timeout=5)
    q_reset = get_item(item_id, token)["quantity"]
    print(f"Reset quantity: {q_reset}")

    statuses = run_phase("OCC", token, item_id, count, mode=None)
    q2 = get_item(item_id, token)["quantity"]
    print(f"After OCC: {q2} (expected >= {q_reset + statuses.count(200)})")

    if q2 >= q_reset + statuses.count(200) and q1 < q0 + count:
        print("PASS: OCC prevents lost updates vs naive.")
        sys.exit(0)
    else:
        print("Check endpoints/data: results not conclusive.")
        sys.exit(2)


if __name__ == "__main__":
    main()