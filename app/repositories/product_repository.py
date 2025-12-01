from typing import List, Optional
from app.extensions import db
from app.models.product import Product
from app.models.warehouse_item import WarehouseItem
from .base import BaseRepository
from app.utils.cache import _make_key, get_json, set_json, delete_key

PRODUCT_LIST_KEY = "products:list"



class ProductRepository(BaseRepository):
    def __init__(self, session=None):
        self.session = session or db.session

    def get_by_id(self, id: int) -> Optional[Product]:
        key = _make_key("product", id)
        cached = get_json(key)
        if cached is not None:
            print(f"🟢 [HIT] Đã tìm thấy Product ID {id} trong Redis!")
            # return plain dict for routes to jsonify
            return Product(**cached)
        else:
            print(f"🔴 [MISS] Product ID {id} không có trong Redis. Truy vấn từ DB...")

        p = self.session.get(Product, id)
        if p:
            try:
                set_json(key, p.to_dict())
                print(f"💾 [SAVE] Đã lưu Product ID {id} vào Redis") # Log khi lưu
            except Exception:
                pass
        return p

    def list(self, **kwargs) -> List[Product]:
        if kwargs:
            # Query DB trực tiếp với filter
            query = self.session.query(Product).filter_by(**kwargs)
            return query.all()

        # cache global product list
        cached = get_json(PRODUCT_LIST_KEY)
        if cached is not None:
            # return list of dicts mapped to Product instances
            return [Product(**d) for d in cached]
        products = self.session.query(Product).all()
        try:
            set_json(PRODUCT_LIST_KEY, [p.to_dict() for p in products])
        except Exception:
            pass
        return products

    def create(self, data: dict) -> Product:
        p = Product(**data)
        self.session.add(p)
        self.session.commit()
        # invalidate list cache
        delete_key(PRODUCT_LIST_KEY)
        return p

    def update(self, id: int, data: dict) -> Optional[Product]:
        from app.utils.occ import occ_execute
        read_sql = "SELECT COALESCE(version,0) AS version FROM products WHERE id = :id"
        read_params = { 'id': id }

        def build_update(expected_version: int):
            set_parts = []
            params = { 'id': id, 'expected_version': expected_version, 'new_version': expected_version + 1 }
            if 'name' in data and data['name'] is not None:
                set_parts.append('name = :name')
                params['name'] = data['name']
            if 'price' in data and data['price'] is not None:
                set_parts.append('price = :price')
                params['price'] = float(data['price'])
            # bump version
            set_parts.append('version = :new_version')
            set_clause = ', '.join(set_parts) if set_parts else 'version = :new_version'
            update_sql = f"""
                UPDATE products
                SET {set_clause}
                WHERE id = :id AND (version = :expected_version OR version IS NULL)
            """
            return update_sql, params
        client_version = data.get('version')
        ok = occ_execute(
            read_sql,
            read_params,
            build_update,
            session=self.session,
            commit=True,
            expected_version_override=client_version if client_version is not None else None
        )
        if not ok:
            return None
        delete_key(PRODUCT_LIST_KEY)
        delete_key(_make_key("product", id))
        return self.session.get(Product, id)

    def delete(self, id: int) -> bool:
        p = self.get_by_id(id)
        if not p:
            return False
        self.session.delete(p)
        self.session.commit()
        # invalidate caches
        delete_key(PRODUCT_LIST_KEY)
        delete_key(_make_key("product", id))
        return True

    def get_stock(self, product_id: int) -> int:
        # returns total quantity across warehouses
        total = self.session.execute(
            db.select(db.func.sum(WarehouseItem.quantity)).filter(WarehouseItem.product_id == product_id)
        ).scalar() or 0
        return int(total)
