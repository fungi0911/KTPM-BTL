import sqlite3
import pymysql

SQLITE_DB = "inventory.db"

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "12345678",  # sửa cho đúng
    "database": "ktpm",
    "charset": "utf8mb4"
}

def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cur = sqlite_conn.cursor()

    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    mysql_cur = mysql_conn.cursor()

    # --- migrate products ---
    sqlite_cur.execute("SELECT id, name, price, version FROM products")
    products = sqlite_cur.fetchall()
    mysql_cur.executemany(
        "INSERT INTO products (id, name, price, version) VALUES (%s, %s, %s, %s)",
        products
    )

    # --- migrate users ---
    sqlite_cur.execute("SELECT id, name, username, password, role, version FROM users")
    users = sqlite_cur.fetchall()
    mysql_cur.executemany(
        "INSERT INTO users (id, name, username, password, role, version) VALUES (%s, %s, %s, %s, %s, %s)",
        users
    )

    # --- migrate warehouses ---
    sqlite_cur.execute("SELECT id, name, version FROM warehouses")
    warehouses = sqlite_cur.fetchall()
    mysql_cur.executemany(
        "INSERT INTO warehouses (id, name, version) VALUES (%s, %s, %s)",
        warehouses
    )

    # --- migrate warehouse_items ---
    sqlite_cur.execute("SELECT id, product_id, warehouse_id, quantity, version FROM warehouse_items")
    items = sqlite_cur.fetchall()
    mysql_cur.executemany(
        "INSERT INTO warehouse_items (id, product_id, warehouse_id, quantity, version) VALUES (%s, %s, %s, %s, %s)",
        items
    )

    mysql_conn.commit()
    print("Migration completed!")

    sqlite_conn.close()
    mysql_conn.close()

if __name__ == "__main__":
    migrate()
