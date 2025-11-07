from ..extensions import db


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    items = db.relationship("WarehouseItem", back_populates="product")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "price": self.price}
