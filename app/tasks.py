import os
from flask import current_app
import matplotlib
from flask.cli import with_appcontext

from app.celery_app import celery
from app.extensions import db
from app.models.warehouse_item import WarehouseItem
from app.repositories import ProductRepository

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@celery.task
@with_appcontext
def generate_barchart(product_id):
    # with current_app.app_context():
    items = WarehouseItem.query.with_entities(
        WarehouseItem.warehouse_id, WarehouseItem.quantity
    ).filter_by(product_id=product_id).all()

    warehouses, quantities = zip(*items) if items else ([], [])

    plt.figure(figsize=(10, 6))
    plt.bar(warehouses, quantities, color='skyblue')
    plt.xlabel("Warehouse")
    plt.ylabel("Quantity")
    plt.title(f"Product '{product_id}' Quantity per Warehouse")
    plt.xticks(rotation=45)
    plt.tight_layout()  # Xuất ra PDF
    folder = "C:/Users/Admin/PycharmProjects/KTPM-BTL/generated_reports"
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"report_{product_id}.pdf")
    plt.savefig(filepath, format='pdf')
    plt.close()
    return {"file_path": filepath}


@celery.task(name="update_product_price")
@with_appcontext
def update_product_price(product_id: int, new_price: float):
    """Cập nhật giá product bất đồng bộ qua Celery, dùng repository để tận dụng OCC + cache."""
    repo = ProductRepository(db.session)
    try:
        updated = repo.update(product_id, {"price": float(new_price)})
    except Exception as e:
        db.session.rollback()
        return {"status": "error", "error": str(e), "product_id": product_id}

    if not updated:
        return {"status": "not_found", "product_id": product_id}

    return {
        "status": "updated",
        "product_id": product_id,
        "price": updated.price,
        "version": updated.version,
    }
