#!/usr/bin/env python3
"""Simple concurrency test for warehouse item updates.

Scenarios:
  1. lost_update: each thread reads quantity then sets quantity = old + 1 via PUT /warehouse_items/<id>
  2. atomic_increment: uses a dedicated endpoint /warehouse_items/<id>/increment to add value atomically.

Usage examples:
  python3.11 concurrency_test.py --item-id 10 --threads 50 --mode lost_update 
  python3.11 concurrency_test.py --item-id 10 --threads 50 --mode atomic_increment 
# Tạo 10 item mới rồi test lost update ngẫu nhiên
python3.11 concurrency_test.py --mode multi_lost_update --threads 100 --multi-count 10
# Dùng sẵn danh sách id
python3.11 concurrency_test.py --mode multi_atomic_increment --threads 100 --item-ids 5,6,7,8
If --item-id is not provided, the script will create a new item (requires JWT token) using warehouse_id=1, product_id=1.

NOTE: This is a lightweight test; true concurrency under WSGI may still serialize due to GIL + SQLite file locking.
"""
import argparse
import threading
import time
import requests
import random  # new import

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
SESSION = None  # global session


def create_item(base_url, token):
    resp = SESSION.post(
        f"{base_url}/warehouse_items/",
        json={"warehouse_id": 1, "product_id": 1, "quantity": 0},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def get_quantity(base_url, item_id, token):
    r = SESSION.get(
        f"{base_url}/warehouse_items/{item_id}",
        timeout=5,
        headers={"Authorization": f"Bearer {token}"} if token else None,
    )
    r.raise_for_status()
    return r.json()["quantity"]


def put_quantity(base_url, item_id, new_q, token):
    r = SESSION.put(
        f"{base_url}/warehouse_items/{item_id}",
        json={"quantity": new_q},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=5,
    )
    r.raise_for_status()


def atomic_increment(base_url, item_id, delta, token):
    r = SESSION.post(
        f"{base_url}/warehouse_items/{item_id}/increment",
        json={"delta": delta},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=5,
    )
    r.raise_for_status()


def create_items(base_url, token, count):
    """Create multiple items and return list of ids."""
    ids = []
    for _ in range(count):
        ids.append(create_item(base_url, token))
    return ids


def get_quantities_sum(base_url, item_ids, token):
    """Sum quantities for a list of item ids."""
    total = 0
    for _id in item_ids:
        total += get_quantity(base_url, _id, token)
    return total


# Workers for multi-item scenario
def multi_lost_update_worker(base_url, item_ids, token):
    try:
        item_id = random.choice(item_ids)
        current = get_quantity(base_url, item_id, token)
        put_quantity(base_url, item_id, current + 1, token)
    except Exception as e:
        print(f"[multi_lost_update_worker] error: {e}")


def multi_atomic_increment_worker(base_url, item_ids, token):
    try:
        item_id = random.choice(item_ids)
        atomic_increment(base_url, item_id, 1, token)
    except Exception as e:
        print(f"[multi_atomic_increment_worker] error: {e}")


def lost_update_worker(base_url, item_id, token):
    # read-modify-write prone to lost update
    try:
        current = get_quantity(base_url, item_id, token)
        new_q = current + 1
        put_quantity(base_url, item_id, new_q, token)
    except Exception as e:
        print(f"[lost_update_worker] error: {e}")


def atomic_increment_worker(base_url, item_id, token):
    try:
        atomic_increment(base_url, item_id, 1, token)
    except Exception as e:
        print(f"[atomic_increment_worker] error: {e}")


def run_threads(fn, threads):
    t_list = [threading.Thread(target=fn) for _ in range(threads)]
    start = time.time()
    for t in t_list:
        t.start()
    for t in t_list:
        t.join()
    return time.time() - start

def login(username, password, base_url):
    resp = requests.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    parser = argparse.ArgumentParser(description="Concurrency test for warehouse item updates")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--item-id", type=int, help="Existing item id to test against", default=1)
    parser.add_argument("--threads", type=int, default=20)
    parser.add_argument("--mode", choices=["lost_update", "atomic_increment", "multi_lost_update", "multi_atomic_increment"], default="lost_update")
    parser.add_argument("--token", help="JWT token for protected endpoints", default=login("admin", "admin123", DEFAULT_BASE_URL))
    parser.add_argument("--multi-count", type=int, default=0, help="Create this many items for multi_* modes if --item-ids not supplied.")
    parser.add_argument("--item-ids", type=str, help="Comma separated existing item ids for multi_* modes.")
    args = parser.parse_args()
    # init session before any helper calls
    global SESSION
    SESSION = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=args.threads, pool_maxsize=args.threads)
    SESSION.mount("http://", adapter)
    SESSION.mount("https://", adapter)
    # --- multi-item setup ---
    multi_item_ids = None
    if args.mode.startswith("multi"):
        if args.item_ids:
            multi_item_ids = [int(x) for x in args.item_ids.split(",") if x.strip()]
        elif args.multi_count > 0:
            # chọn ngẫu nhiên n id sẵn có trong khoảng 1..30000 (không tạo mới)
            max_range = 30000
            if args.multi_count > max_range:
                parser.error(f"--multi-count must be <= {max_range}")
            multi_item_ids = random.sample(range(1, max_range + 1), args.multi_count)
            print(f"[setup] Selected {args.multi_count} existing item ids (random 1..{max_range}): {multi_item_ids}")
        else:
            parser.error("Multi mode requires --item-ids or --multi-count > 0")
    # --- single item path unchanged ---
    item_id = args.item_id
    if not args.mode.startswith("multi"):
        if item_id is None:
            if not args.token:
                parser.error("Creating a new item requires --token")
            print("[setup] Creating test item...")
            item_id = create_item(args.base_url, args.token)
            print(f"[setup] Created item id={item_id}")
        initial = get_quantity(args.base_url, item_id, args.token)
        print(f"[info] Initial: {initial}")
        if args.mode == "lost_update":
            print(f"[run] Giả lập luồng {args.threads} lost_update đồng thời...")
            elapsed = run_threads(lambda: lost_update_worker(args.base_url, item_id, args.token), args.threads)
        else:
            print(f"[run] Giả lập {args.threads} luồng tăng số lượng..")
            elapsed = run_threads(lambda: atomic_increment_worker(args.base_url, item_id, args.token), args.threads)
        final_q = get_quantity(args.base_url, item_id, args.token)
        print(f"[result]: {final_q}")
        expected = initial + args.threads
        if args.mode == "lost_update":
            print(f"[analysis] Expected ≈ {expected}. Actual {final_q}. Lost updates: {expected - final_q}")
        else:
            print(f"[analysis] Atomic mode expected {expected}. Delta: {final_q - expected}")
        print(f"[timing] Elapsed: {elapsed:.3f}s")
    else:
        # multi-item scenario
        initial_sum = get_quantities_sum(args.base_url, multi_item_ids, args.token)
        print(f"[info] Initial total quantity (sum over {len(multi_item_ids)} items): {initial_sum}")
        if args.mode == "multi_lost_update":
            print(f"[run] Giả lập {args.threads} luồng lost_update ngẫu nhiên trên {len(multi_item_ids)} items...")
            elapsed = run_threads(lambda: multi_lost_update_worker(args.base_url, multi_item_ids, args.token), args.threads)
        else:
            print(f"[run] Giả lập {args.threads} luồng atomic_increment ngẫu nhiên trên {len(multi_item_ids)} items...")
            elapsed = run_threads(lambda: multi_atomic_increment_worker(args.base_url, multi_item_ids, args.token), args.threads)
        final_sum = get_quantities_sum(args.base_url, multi_item_ids, args.token)
        print(f"[result] Total sum: {final_sum}")
        expected_sum = initial_sum + args.threads
        if args.mode == "multi_lost_update":
            print(f"[analysis] Expected sum ≈ {expected_sum}. Actual {final_sum}. Lost increments: {expected_sum - final_sum}")
        else:
            print(f"[analysis] Atomic expected sum {expected_sum}. Delta: {final_sum - expected_sum}")
        print(f"[timing] Elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()
