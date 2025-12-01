import os
from flask import current_app, jsonify
import matplotlib
from flask.cli import with_appcontext

from app.celery_app import celery
from app.extensions import db
from app.models.warehouse_item import WarehouseItem
from app.repositories import ProductRepository
from app.utils.occ import occ_execute

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@celery.task
@with_appcontext
def generate_barchart(product_id):
    # with current_app.app_context():
    items = WarehouseItem.query.with_entities(
        WarehouseItem.warehouse_id, WarehouseItem.quantity
    ).filter_by(product_id=product_id).all()

    if items is None:
        return {"message": "No items found"}

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
    return {"message": "success", "file_path": filepath}


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

@celery.task
@with_appcontext
def update_product_quantity(item_id: int, delta: int, client_version: int, mode: str):
    if mode == 'naive':
        res = db.session.execute(
            db.text("UPDATE warehouse_items SET quantity = quantity + :delta WHERE id = :id"),
            {'delta': delta, 'id': item_id}
        )
        db.session.commit()
        from app.utils.cache import delete_key, _make_key
        delete_key(_make_key("warehouse_item", item_id))
        delete_key("warehouse_items:list")
        delete_key("stats:products")
        delete_key("stats:warehouses")
        return jsonify({
            'item_id': item_id,
            'delta': delta,
            'status': 'updated-naive',
            'rowcount': res.rowcount
        })

    # Generic OCC executor: routes define SQL builder, OCC handles retries
    read_sql = "SELECT COALESCE(version, 0) AS version FROM warehouse_items WHERE id = :id"
    read_params = {'id': item_id}

    def build_update(expected_version: int):
        update_sql = """
                     UPDATE warehouse_items
                     SET quantity = quantity + :delta, \
                         version  = :new_version
                     WHERE id = :id \
                       AND (version = :expected_version OR version IS NULL) \
                     """
        update_params = {
            'id': item_id,
            'delta': delta,
            'expected_version': expected_version,
            'new_version': expected_version + 1,
        }
        return update_sql, update_params

    ok = occ_execute(
        read_sql,
        read_params,
        build_update,
        session=db.session,
        expected_version_override=client_version
    )
    if not ok:
        return jsonify({'msg': 'conflict or not found, please retry later'}), 409

    # invalidate cache for this item and stats
    from app.utils.cache import delete_key, _make_key
    delete_key(_make_key("warehouse_item", item_id))
    delete_key("warehouse_items:list")
    delete_key("stats:products")
    delete_key("stats:warehouses")
    return jsonify({
        "item_id": item_id,
        "delta": delta,
        "status": "updated"
    })
