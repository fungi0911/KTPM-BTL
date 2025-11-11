#!/usr/bin/env python3
"""Simple concurrency test for warehouse item updates.

Scenarios:
  1. lost_update: each thread reads quantity then sets quantity = old + 1 via PUT /warehouse_items/<id>
  2. atomic_increment: uses a dedicated endpoint /warehouse_items/<id>/increment to add value atomically.

Usage examples:
  python concurrency_test.py --item-id 10 --threads 50 --mode lost_update 
  python concurrency_test.py --item-id 10 --threads 50 --mode atomic_increment 

If --item-id is not provided, the script will create a new item (requires JWT token) using warehouse_id=1, product_id=1.

NOTE: This is a lightweight test; true concurrency under WSGI may still serialize due to GIL + SQLite file locking.
"""
import argparse
import threading
import time
import requests

DEFAULT_BASE_URL = "http://127.0.0.1:5000"


def create_item(base_url, token):
    resp = requests.post(
        f"{base_url}/warehouse_items/",
        json={"warehouse_id": 1, "product_id": 1, "quantity": 0},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def get_quantity(base_url, item_id, token):
    r = requests.get(f"{base_url}/warehouse_items/{item_id}", timeout=5, headers={"Authorization": f"Bearer {token}"} if token else None)
    r.raise_for_status()
    return r.json()["quantity"]


def put_quantity(base_url, item_id, new_q, token):
    r = requests.put(
        f"{base_url}/warehouse_items/{item_id}",
        json={"quantity": new_q},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=5,
    )
    r.raise_for_status()


def atomic_increment(base_url, item_id, delta, token):
    r = requests.post(
        f"{base_url}/warehouse_items/{item_id}/increment",
        json={"delta": delta},
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=5,
    )
    r.raise_for_status()


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
    parser.add_argument("--mode", choices=["lost_update", "atomic_increment"], default="lost_update")
    parser.add_argument("--token", help="JWT token for protected endpoints", default=login("admin", "admin123", DEFAULT_BASE_URL))
    args = parser.parse_args()
    item_id = args.item_id
    if item_id is None:
        if not args.token:
            parser.error("Creating a new item requires --token")
        print("[setup] Creating test item...")
        item_id = create_item(args.base_url, args.token)
        print(f"[setup] Created item id={item_id}")
    # initial quantity
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


if __name__ == "__main__":
    main()
