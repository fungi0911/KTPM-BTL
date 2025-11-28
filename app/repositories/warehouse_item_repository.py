from typing import List, Optional
from app.extensions import db
from app.models.warehouse_item import WarehouseItem
from .base import BaseRepository
from app.utils.cache import _make_key, get_json, set_json, delete_key

ITEM_LIST_KEY = "warehouse_items:list"
STATS_PRODUCTS_KEY = "stats:products"
STATS_WAREHOUSES_KEY = "stats:warehouses"


class WarehouseItemRepository(BaseRepository):
    def __init__(self, session=None):
        self.session = session or db.session

    def get_by_id(self, id: int) -> Optional[WarehouseItem]:
        key = _make_key("warehouse_item", id)
        cached = get_json(key)
        if cached is not None:
            return cached
        it = self.session.get(WarehouseItem, id)
        if it:
            set_json(key, it.to_dict())
        return it

    def list(self, **kwargs) -> List[WarehouseItem]:
        print("Chay vao ham list trong WarehouseItemRepository")
        cached = get_json(ITEM_LIST_KEY)
        if cached is not None:
            return cached
        rows = self.session.query(WarehouseItem).all()
        set_json(ITEM_LIST_KEY, [r.to_dict() for r in rows])
        return rows

    def create(self, data: dict) -> WarehouseItem:
        it = WarehouseItem(**data)
        self.session.add(it)
        self.session.commit()
        delete_key(ITEM_LIST_KEY)
        delete_key(STATS_PRODUCTS_KEY)
        delete_key(STATS_WAREHOUSES_KEY)
        return it

    def update(self, id: int, data: dict) -> Optional[WarehouseItem]:
        it = self.get_by_id(id)
        if not it:
            return None
        for k, v in data.items():
            if hasattr(it, k):
                setattr(it, k, v)
        self.session.commit()
        delete_key(ITEM_LIST_KEY)
        delete_key(_make_key("warehouse_item", id))
        delete_key(STATS_PRODUCTS_KEY)
        delete_key(STATS_WAREHOUSES_KEY)
        return it

    def delete(self, id: int) -> bool:
        it = self.get_by_id(id)
        if not it:
            return False
        self.session.delete(it)
        self.session.commit()
        delete_key(ITEM_LIST_KEY)
        delete_key(_make_key("warehouse_item", id))
        delete_key(STATS_PRODUCTS_KEY)
        delete_key(STATS_WAREHOUSES_KEY)
        return True

    def product_stock_stats(self):
        cached = get_json(STATS_PRODUCTS_KEY)
        if cached is not None:
            return cached
        rows = self.session.execute(
            db.select(
                WarehouseItem.product_id,
                db.func.sum(WarehouseItem.quantity).label('total_qty')
            ).group_by(WarehouseItem.product_id)
        ).all()
        result = [
            {
                'product_id': r[0], 
                'total_quantity': float(r[1]) if r[1] is not None else 0
            } 
            for r in rows
        ]
        set_json(STATS_PRODUCTS_KEY, result)
        return result

    def warehouse_stock_stats(self):
        cached = get_json(STATS_WAREHOUSES_KEY)
        if cached is not None:
            return cached
        rows = self.session.execute(
            db.select(
                WarehouseItem.warehouse_id,
                db.func.sum(WarehouseItem.quantity).label('total_qty')
            ).group_by(WarehouseItem.warehouse_id)
        ).all()
        result = [
            {
                'warehouse_id': r[0], 
                'total_quantity': float(r[1]) if r[1] is not None else 0
            } 
            for r in rows
        ]
        set_json(STATS_WAREHOUSES_KEY, result)
        return result
