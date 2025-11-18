#!/usr/bin/env python3
"""Direct raw SQLite data spawner for inventory.db

This bypasses SQLAlchemy and writes straight into the database file defined in Config:
Default path (from Config): /Users/atula/Desktop/KTPM_BTL/inventory.db

Usage examples:
  python spawn_sqlite.py --reset --users 10 --products 50 --warehouses 5 --items 200
  python spawn_sqlite.py --products 30 --append
  python spawn_sqlite.py --ensure-admin

Options:
  --users N            Number of users to ensure/append
  --products N         Number of products
  --warehouses N       Number of warehouses
  --items N            Number of warehouse_items
  --reset              Drop all existing tables first (DANGEROUS)
  --append             Append up to reaching counts (instead of skipping when existing)
  --ensure-admin       Create an admin user (username=admin, password=admin123) if missing
  --db PATH            Override database file path

Notes:
  - Uses PRAGMA foreign_keys=ON
  - Simple random generation; uses Faker if available, otherwise falls back to basic names.
"""

import argparse
import os
import random
import sqlite3
from typing import List

try:
    from faker import Faker
    faker = Faker()
except Exception:  # Faker not installed
    faker = None

DEFAULT_DB = "instance/inventory.db"
DEFAULT_USERS = 5
DEFAULT_PRODUCTS = 20
DEFAULT_WAREHOUSES = 3
DEFAULT_ITEMS = 100000
ROLES = ["staff", "manager", "admin"]

SCHEMA_SQL = [
    # users
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'staff'
    );
    """,
    # products
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL
    );
    """,
    # warehouses
    """
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
    """,
    # warehouse_items
    """
    CREATE TABLE IF NOT EXISTS warehouse_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        warehouse_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE
    );
    """,
]

DROP_SQL = [
    "DROP TABLE IF EXISTS warehouse_items;",
    "DROP TABLE IF EXISTS users;",
    "DROP TABLE IF EXISTS products;",
    "DROP TABLE IF EXISTS warehouses;",
]


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    for stmt in SCHEMA_SQL:
        cur.executescript(stmt)
    conn.commit()


def drop_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    for stmt in DROP_SQL:
        cur.execute(stmt)
    conn.commit()


def existing_count(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def gen_username(i: int) -> str:
    if faker:
        return f"{faker.user_name()}{i}"[:30]
    return f"user{i}"


def gen_product_name(i: int) -> str:
    if faker:
        return faker.unique.word().capitalize()[:50]
    return f"Product_{i}"


def insert_users(conn: sqlite3.Connection, target: int, append: bool):
    cur = conn.cursor()
    current = existing_count(conn, "users")
    if current >= target and not append:
        print(f"[users] Skip (current={current} >= target={target})")
        return
    needed = target - current if append and current < target else (target if current == 0 else 0)
    if needed <= 0 and append:
        print(f"[users] Already at or above target ({current})")
        return
    to_create = needed if append else (target if current == 0 else 0)
    if to_create <= 0:
        print("[users] Nothing to create")
        return
    print(f"[users] Inserting {to_create} users...")
    for i in range(to_create):
        name = faker.name() if faker else f"User {i}" if i < 50 else f"User{i}"
        username = gen_username(i + current)
        role = random.choice(ROLES)
        password = "123456"  # plaintext per current model
        cur.execute(
            "INSERT INTO users(name, username, password, role) VALUES (?, ?, ?, ?)",
            (name, username, password, role)
        )
    conn.commit()


def ensure_admin(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username='admin'")
    if cur.fetchone():
        print("[admin] Existing admin user found")
        return
    print("[admin] Creating admin user (username=admin, password=admin123, role=admin)")
    cur.execute(
        "INSERT INTO users(name, username, password, role) VALUES (?,?,?,?)",
        ("Administrator", "admin", "admin123", "admin")
    )
    conn.commit()


def insert_products(conn: sqlite3.Connection, target: int, append: bool):
    cur = conn.cursor()
    current = existing_count(conn, "products")
    if current >= target and not append:
        print(f"[products] Skip (current={current} >= target={target})")
        return
    needed = target - current if append and current < target else (target if current == 0 else 0)
    to_create = needed if append else (target if current == 0 else 0)
    if to_create <= 0:
        print("[products] Nothing to create")
        return
    print(f"[products] Inserting {to_create} products...")
    for i in range(to_create):
        name = gen_product_name(i + current)
        price = round(random.uniform(5, 500), 2)
        cur.execute("INSERT INTO products(name, price) VALUES (?, ?)", (name, price))
    conn.commit()


def insert_warehouses(conn: sqlite3.Connection, target: int, append: bool):
    cur = conn.cursor()
    current = existing_count(conn, "warehouses")
    if current >= target and not append:
        print(f"[warehouses] Skip (current={current} >= target={target})")
        return
    needed = target - current if append and current < target else (target if current == 0 else 0)
    to_create = needed if append else (target if current == 0 else 0)
    if to_create <= 0:
        print("[warehouses] Nothing to create")
        return
    print(f"[warehouses] Inserting {to_create} warehouses...")
    for i in range(to_create):
        cur.execute("INSERT INTO warehouses(name) VALUES (?)", (f"Warehouse {i + current + 1}",))
    conn.commit()


def fetch_ids(conn: sqlite3.Connection, table: str) -> List[int]:
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM {table}")
    return [row[0] for row in cur.fetchall()]


def insert_items(conn: sqlite3.Connection, target: int, append: bool):
    cur = conn.cursor()
    current = existing_count(conn, "warehouse_items")
    if current >= target and not append:
        print(f"[items] Skip (current={current} >= target={target})")
        return
    needed = target - current if append and current < target else (target if current == 0 else 0)
    to_create = needed if append else (target if current == 0 else 0)
    if to_create <= 0:
        print("[items] Nothing to create")
        return
    product_ids = fetch_ids(conn, "products")
    warehouse_ids = fetch_ids(conn, "warehouses")
    if not product_ids or not warehouse_ids:
        print("[items] Cannot create items (need products & warehouses)")
        return
    print(f"[items] Inserting {to_create} warehouse_items...")
    batch = []
    for _ in range(to_create):
        batch.append((random.choice(product_ids), random.choice(warehouse_ids), random.randint(1, 200)))
    cur.executemany("INSERT INTO warehouse_items(product_id, warehouse_id, quantity) VALUES (?,?,?)", batch)
    conn.commit()


def summary(conn: sqlite3.Connection):
    print("\n[summary]")
    for t in ["users", "products", "warehouses", "warehouse_items"]:
        print(f"  {t}: {existing_count(conn, t)}")


def parse_args():
    p = argparse.ArgumentParser(description="Raw SQLite spawner")
    p.add_argument("--db", default=DEFAULT_DB, help="Path to inventory.db")
    p.add_argument("--users", type=int, default=DEFAULT_USERS)
    p.add_argument("--products", type=int, default=DEFAULT_PRODUCTS)
    p.add_argument("--warehouses", type=int, default=DEFAULT_WAREHOUSES)
    p.add_argument("--items", type=int, default=DEFAULT_ITEMS)
    p.add_argument("--reset", action="store_true", help="Drop all tables first")
    p.add_argument("--append", action="store_true", help="Append until reaching target counts")
    p.add_argument("--ensure-admin", action="store_true", help="Ensure an admin user exists")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    conn = connect(args.db)

    if args.reset:
        print("[reset] Dropping all tables...")
        drop_all(conn)

    print("[schema] Ensuring tables...")
    ensure_schema(conn)

    insert_users(conn, args.users, append=args.append)
    if args.ensure_admin:
        ensure_admin(conn)
    insert_products(conn, args.products, append=args.append)
    insert_warehouses(conn, args.warehouses, append=args.append)
    insert_items(conn, args.items, append=args.append)

    summary(conn)
    conn.close()
    print("[done] Raw spawn finished.")


if __name__ == "__main__":
    main()


# Example usage
# python spawn_sqlite.py --users 15 --products 80 --warehouses 6 --items 300 --ensure-admin --append

