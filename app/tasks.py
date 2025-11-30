import os
from flask import current_app
import matplotlib
from flask.cli import with_appcontext

from app.celery_app import celery
from app.models.warehouse_item import WarehouseItem

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
