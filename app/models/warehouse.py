from ..extensions import db


class Warehouse(db.Model):
    __tablename__ = "warehouses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    items = db.relationship("WarehouseItem", back_populates="warehouse")
    version = db.Column(db.Integer, nullable=True, default=0)
    def to_dict(self):
        return {"id": self.id, "name": self.name, "version": self.version}
