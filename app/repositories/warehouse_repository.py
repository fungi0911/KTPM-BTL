from typing import List, Optional
from app.extensions import db
from app.models.warehouse import Warehouse
from app.models.warehouse_item import WarehouseItem
from .base import BaseRepository
from app.utils.cache import _make_key, get_json, set_json, delete_key

WAREHOUSE_LIST_KEY = "warehouses:list"


class WarehouseRepository(BaseRepository):
    def __init__(self, session=None):
        self.session = session or db.session

    def get_by_id(self, id: int) -> Optional[Warehouse]:
        key = _make_key("warehouse", id)
        cached = get_json(key)
        if cached is not None:
            return Warehouse(**cached)
        w = self.session.get(Warehouse, id)
        if w:
            set_json(key, w.to_dict())
        return w

    def list(self, **kwargs) -> List[Warehouse]:
        cached = get_json(WAREHOUSE_LIST_KEY)
        if cached is not None:
            return [Warehouse(**d) for d in cached]
        rows = self.session.query(Warehouse).all()
        set_json(WAREHOUSE_LIST_KEY, [r.to_dict() for r in rows])
        return rows

    def create(self, data: dict) -> Warehouse:
        w = Warehouse(**data)
        self.session.add(w)
        self.session.commit()
        delete_key(WAREHOUSE_LIST_KEY)
        return w

    def update(self, id: int, data: dict) -> Optional[Warehouse]:
        w = self.get_by_id(id)
        if not w:
            return None
        if 'name' in data:
            w.name = data['name']
        self.session.commit()
        delete_key(WAREHOUSE_LIST_KEY)
        delete_key(_make_key("warehouse", id))
        return w

    def delete(self, id: int) -> bool:
        w = self.get_by_id(id)
        if not w:
            return False
        self.session.delete(w)
        self.session.commit()
        delete_key(WAREHOUSE_LIST_KEY)
        delete_key(_make_key("warehouse", id))
        return True

    def get_items_for_warehouse(self, warehouse_id: int, product_id: Optional[int] = None):
        q = self.session.query(WarehouseItem).filter(WarehouseItem.warehouse_id == warehouse_id)
        if product_id:
            q = q.filter(WarehouseItem.product_id == product_id)
        return q.all()
