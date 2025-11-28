from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Iterable, List
from pymongo.collection import Collection
from pymongo import ReturnDocument
import threading, time
from flask import current_app

from ..extensions import mongo_client, db as sql_db
from ..config import Config

ITEM_COLL = "item_events"
PROD_COLL = "product_events"
WH_COLL = "warehouse_events"


def _db():
    if mongo_client is None:
        raise RuntimeError("Mongo client not initialized")
    return mongo_client[Config.MONGO_DB]


def init_event_store():
    db = _db()

    # --- Events cho từng loại ---
    # Item events: lookup nhanh theo item_id (stream có thể là item:<id>)
    db[ITEM_COLL].create_index([("stream", 1), ("version", 1)], unique=True)
    db[ITEM_COLL].create_index("payload.product_id")
    db[ITEM_COLL].create_index("payload.warehouse_id")

    # Product events: lookup nhanh theo product_id
    db[PROD_COLL].create_index([("stream", 1), ("version", 1)], unique=True)
    db[PROD_COLL].create_index("payload.product_id")

    # Warehouse events: lookup nhanh theo warehouse_id
    db[WH_COLL].create_index([("stream", 1), ("version", 1)], unique=True)
    db[WH_COLL].create_index("payload.warehouse_id")

    print("Event store indexes initialized")


def get_coll(event_type: str) -> Collection:
    db = _db()
    if event_type.startswith("WarehouseItem"):
        return db[ITEM_COLL]
    elif event_type.startswith("Product"):
        return db[PROD_COLL]
    elif event_type.startswith("Warehouse"):
        return db[WH_COLL]
    else:
        raise ValueError(f"Unknown event type: {event_type}")


def append_event(stream: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append an event and update projections.

    stream example: warehouse_item:123
    version is obtained by counting existing events for the stream (naive; better use findOneAndUpdate counter doc).
    """
    db = _db()
    events = get_coll(event_type)
    counters = db["event_counters"]

    counter = counters.find_one_and_update(
        {"stream": stream},
        {"$inc": {"version": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    version = counter["version"]

    doc = {
        "stream": stream,
        "version": version,
        "type": event_type,
        "payload": payload,
        "ts": datetime.utcnow(),
    }
    events.insert_one(doc)
    return doc

def apply_events_for_stream(stream: str):
    """Apply all not-yet-applied events for a given stream.

    Uses optimistic locking (version check) so that concurrent threads
    processing the same stream will not double-apply the same event.
    """
    db = _db()
    coll = db[ITEM_COLL]
    item_id = int(stream.split(":")[1])

    # lấy version đã apply gần nhất (mặc định 0 nếu NULL)
    last_applied = sql_db.session.execute(
        sql_db.text("SELECT COALESCE(version, 0) FROM warehouse_items WHERE id = :id"),
        {'id': item_id}
    ).scalar() or 0

    events = coll.find({"stream": stream, "version": {"$gt": last_applied}}).sort("version", 1)

    for ev in events:
        # _apply_projection sẽ tự xử lý update với điều kiện version = current_version
        applied = _apply_projection(ev["type"], ev["payload"], ev["version"])
        if applied:
            sql_db.session.commit()
        else:
            # sự kiện đã được thread khác apply -> bỏ qua tiếp
            continue


def _apply_projection(event_type: str, payload: Dict[str, Any], version: int) -> bool:
    """Apply projection with optimistic version check.

    Returns True nếu apply thành công, False nếu bị race (đã apply ở nơi khác).
    """
    if event_type == "WarehouseItemDecremented":
        return _on_item_decremented(payload, version)
    elif event_type == "WarehouseItemIncremented":
        return _on_item_incremented(payload, version)
    return False


def _on_item_decremented(p: Dict[str, Any], new_version: int) -> bool:
    item_id = p["id"]
    delta = p["delta"]
    prev_version = new_version - 1
    res = sql_db.session.execute(
        sql_db.text(
            """
            UPDATE warehouse_items
            SET quantity = quantity - :delta, version = :new_version
            WHERE id = :id AND (version = :prev_version OR version IS NULL)
            """
        ),
        {'delta': delta, 'new_version': new_version, 'prev_version': prev_version, 'id': item_id}
    )
    return res.rowcount == 1


def _on_item_incremented(p: Dict[str, Any], new_version: int) -> bool:
    item_id = p["id"]
    delta = p["delta"]
    prev_version = new_version - 1
    res = sql_db.session.execute(
        sql_db.text(
            """
            UPDATE warehouse_items
            SET quantity = quantity + :delta, version = :new_version
            WHERE id = :id AND (version = :prev_version OR version IS NULL)
            """
        ),
        {'delta': delta, 'new_version': new_version, 'prev_version': prev_version, 'id': item_id}
    )
    return res.rowcount == 1


def apply_events_for_rows(rows: List[Any]) -> List[Any]:
    """Batch refresh nhiều warehouse item rows.

    Nhận list các row (dict hoặc object có thuộc tính id, version). Với mỗi row:
    - Lấy stream tương ứng warehouse_item:<id>.
    - Dùng event_counters check nhanh có event mới.
    - Nếu có: tải events mới và apply với optimistic locking.
    - Nếu apply thành công: reload lại quantity, version.

    Trả về: CHÍNH danh sách rows truyền vào (đủ số lượng ban đầu), với các row
    đã được cập nhật giá trị mới nếu có event; row không đổi giữ nguyên.
    """
    db = _db()
    coll = db[ITEM_COLL]
    counters = db["event_counters"]

    for row in rows:
        # Hỗ trợ dict hoặc ORM object
        item_id = getattr(row, 'id', None) if not isinstance(row, dict) else row.get('id')
        if item_id is None:
            continue  # bỏ qua row không hợp lệ
        current_version = getattr(row, 'version', None) if not isinstance(row, dict) else row.get('version')
        current_version = current_version or 0
        stream = f"warehouse_item:{item_id}"

        # Dùng event_counters để kiểm tra nhanh có event mới hay không
        counter_doc = counters.find_one({"stream": stream})
        if not counter_doc:
            continue  # chưa có event nào cho stream này
        latest_version = counter_doc.get("version", 0)
        if latest_version <= current_version:
            continue  # không có event mới

        events = coll.find({"stream": stream, "version": {"$gt": current_version}}).sort("version", 1)
        changed = False
        for ev in events:
            applied = _apply_projection(ev["type"], ev["payload"], ev["version"])
            if applied:
                sql_db.session.commit()
                changed = True

        if changed:
            fresh = sql_db.session.execute(
                sql_db.text("SELECT id, quantity, version FROM warehouse_items WHERE id = :id"),
                {'id': item_id}
            ).mappings().first()
            if fresh:
                if isinstance(row, dict):
                    row.update(fresh)
                else:
                    setattr(row, 'quantity', fresh['quantity'])
                    setattr(row, 'version', fresh['version'])

    return rows
