
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Iterable
from pymongo.collection import Collection
from pymongo import ReturnDocument

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
    db = _db()
    coll = db[ITEM_COLL]
    item_id = int(stream.split(":")[1])

    # lấy version đã apply gần nhất
    last_applied = sql_db.session.execute(
        sql_db.text("SELECT version FROM warehouse_items WHERE id = :id"),
        {'id': item_id}
    ).scalar() or 0

    events = coll.find({"stream": stream, "version": {"$gt": last_applied}}).sort("version", 1)

    for ev in events:
        _apply_projection(ev["type"], ev["payload"])
        sql_db.session.execute(
            sql_db.text("UPDATE warehouse_items SET version = :v WHERE id = :id"),
            {'v': ev["version"], 'id': item_id}
        )
        sql_db.session.commit()


def _apply_projection(event_type: str, payload: Dict[str, Any]):
    if event_type == "WarehouseItemDecremented":
        _on_item_decremented(payload)
    elif event_type == "WarehouseItemIncremented":
        _on_item_incremented(payload)


def _on_item_decremented(p: Dict[str, Any]):
    item_id = p["id"]
    delta = p["delta"]
    sql_db.session.execute(
        sql_db.text("UPDATE warehouse_items SET quantity = quantity - :delta WHERE id = :id"),
        {'delta': delta, 'id': item_id}
    )
    sql_db.session.commit()


def _on_item_incremented(p: Dict[str, Any]):
    item_id = p["id"]
    delta = p["delta"]
    sql_db.session.execute(
        sql_db.text("UPDATE warehouse_items SET quantity = quantity + :delta WHERE id = :id"),
        {'delta': delta, 'id': item_id}
    )
    sql_db.session.commit()
