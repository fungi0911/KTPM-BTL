from ..extensions import db
class WarehouseItem(db.Model):
    __tablename__ = "warehouse_items"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    warehouse = db.relationship("Warehouse", back_populates="items")
    product = db.relationship("Product", back_populates="items")
