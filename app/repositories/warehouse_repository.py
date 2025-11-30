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
        from app.utils.occ import occ_execute
        read_sql = "SELECT COALESCE(version,0) AS version FROM warehouses WHERE id = :id"
        read_params = { 'id': id }

        def build_update(expected_version: int):
            set_parts = []
            params = { 'id': id, 'expected_version': expected_version, 'new_version': expected_version + 1 }
            if 'name' in data and data['name'] is not None:
                set_parts.append('name = :name')
                params['name'] = data['name']
            set_parts.append('version = :new_version')
            set_clause = ', '.join(set_parts) if set_parts else 'version = :new_version'
            update_sql = f"""
                UPDATE warehouses
                SET {set_clause}
                WHERE id = :id AND (version = :expected_version OR version IS NULL)
            """
            return update_sql, params

        ok = occ_execute(read_sql, read_params, build_update, session=self.session, commit=True)
        if not ok:
            return None
        delete_key(WAREHOUSE_LIST_KEY)
        delete_key(_make_key("warehouse", id))
        return self.session.get(Warehouse, id)

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
