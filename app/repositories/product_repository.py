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
            # return plain dict for routes to jsonify
            return Product(**cached) if isinstance(cached, dict) else cached
        p = self.session.get(Product, id)
        if p:
            try:
                set_json(key, p.to_dict())
            except Exception:
                pass
        return p

    def list(self, **kwargs) -> List[Product]:
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
        p = self.get_by_id(id)
        if not p:
            return None
        for k, v in data.items():
            if hasattr(p, k):
                setattr(p, k, v)
        self.session.commit()
        # invalidate caches
        delete_key(PRODUCT_LIST_KEY)
        delete_key(_make_key("product", id))
        return p

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
