from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.event_store.event_store import append_event, apply_events_for_stream
from ..models.warehouse_item import WarehouseItem
from ..models.product import Product
from ..models.warehouse import Warehouse
from ..extensions import db

item_bp = Blueprint("item", __name__, url_prefix="/warehouse_items")

@item_bp.route('/', methods=['GET'])
def get_warehouse_items():
    """Get all warehouse items
    ---
    tags:
      - Warehouse Items
    responses:
      200:
        description: List of warehouse items with warehouse & product info
    """
    stream = f"warehouse_item"
    apply_events_for_stream(stream)
    items = WarehouseItem.query.all()
    return jsonify([i.to_dict() for i in items])

@item_bp.route('/search', methods=['GET'])
def search_items():
    """Search warehouse items with filters & pagination
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: warehouse_id
        in: query
        type: integer
      - name: product_id
        in: query
        type: integer
      - name: min_qty
        in: query
        type: integer
      - name: max_qty
        in: query
        type: integer
      - name: page
        in: query
        type: integer
      - name: page_size
        in: query
        type: integer
    responses:
      200:
        description: Filtered list with metadata
    """
    q = WarehouseItem.query
    # filters
    def as_int(name):
        val = request.args.get(name)
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    warehouse_id = as_int('warehouse_id')
    product_id = as_int('product_id')
    min_qty = as_int('min_qty')
    max_qty = as_int('max_qty')
    page = as_int('page') or 1
    page_size = as_int('page_size') or 20

    if warehouse_id:
        q = q.filter(WarehouseItem.warehouse_id == warehouse_id)
    if product_id:
        q = q.filter(WarehouseItem.product_id == product_id)
    if min_qty is not None:
        q = q.filter(WarehouseItem.quantity >= min_qty)
    if max_qty is not None:
        q = q.filter(WarehouseItem.quantity <= max_qty)

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': [i.to_dict() for i in items]
    })

@item_bp.route('/stats/products', methods=['GET'])
def product_stock_stats():
    """Aggregate total quantity per product across all warehouses
    ---
    tags:
      - Warehouse Items
    responses:
      200:
        description: List of product stock totals
    """
    rows = db.session.execute(
        db.select(
            WarehouseItem.product_id,
            db.func.sum(WarehouseItem.quantity).label('total_qty')
        ).group_by(WarehouseItem.product_id)
    ).all()
    # fetch product names map
    prod_map = {p.id: p.name for p in Product.query.filter(Product.id.in_([r[0] for r in rows])).all()}
    return jsonify([
        {'product_id': r[0], 'product': prod_map.get(r[0]), 'total_quantity': r[1]} for r in rows
    ])

@item_bp.route('/stats/warehouses', methods=['GET'])
def warehouse_stock_stats():
    """Aggregate total quantity per warehouse
    ---
    tags:
      - Warehouse Items
    responses:
      200:
        description: List of warehouse stock totals
    """
    rows = db.session.execute(
        db.select(
            WarehouseItem.warehouse_id,
            db.func.sum(WarehouseItem.quantity).label('total_qty')
        ).group_by(WarehouseItem.warehouse_id)
    ).all()
    wh_map = {w.id: w.name for w in Warehouse.query.filter(Warehouse.id.in_([r[0] for r in rows])).all()}
    return jsonify([
        {'warehouse_id': r[0], 'warehouse': wh_map.get(r[0]), 'total_quantity': r[1]} for r in rows
    ])

@item_bp.route('/', methods=['POST'])
@jwt_required()
def create_warehouse_item():
    """Add product to warehouse
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            warehouse_id: {type: integer}
            product_id: {type: integer}
            quantity: {type: integer}
    responses:
      201:
        description: Warehouse item created successfully
    """
    data = request.json
    item = WarehouseItem(**data)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@item_bp.route('/<int:item_id>', methods=['GET'])
def get_warehouse_item(item_id):
    """Get warehouse item by ID
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: item_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Warehouse item object
      404:
        description: Not found
    """
    stream = f"warehouse_item:{item_id}"
    apply_events_for_stream(stream)
    item = WarehouseItem.query.get_or_404(item_id)
    return jsonify(item.to_dict())

@item_bp.route('/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_warehouse_item(item_id):
    """Update warehouse item (quantity or reassignment)
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: item_id
        in: path
        required: true
        type: integer
      - name: body
        in: body
        schema:
          type: object
          properties:
            quantity: {type: integer}
            product_id: {type: integer}
            warehouse_id: {type: integer}
    responses:
      200:
        description: Updated warehouse item
      404:
        description: Not found
    """
    item = WarehouseItem.query.get_or_404(item_id)
    data = request.json or {}
    if 'quantity' in data:
        item.quantity = data['quantity']
    if 'product_id' in data:
        item.product_id = data['product_id']
    if 'warehouse_id' in data:
        item.warehouse_id = data['warehouse_id']
    db.session.commit()
    return jsonify(item.to_dict())

@item_bp.route('/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_warehouse_item(item_id):
    """Delete warehouse item
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: item_id
        in: path
        required: true
        type: integer
    responses:
      204:
        description: Deleted successfully
      404:
        description: Not found
    """
    item = WarehouseItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'deleted', 'item_id': item_id}), 200

@item_bp.route('/<int:item_id>/increment', methods=['POST'])
@jwt_required()
def increment_item_quantity(item_id):
    """Atomically increment quantity of a warehouse item.
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: item_id
        in: path
        required: true
        type: integer
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            delta: {type: integer, description: "Amount to add (can be negative)"}
    responses:
      200:
        description: Updated item with new quantity
      404:
        description: Not found
    """
    data = request.json or {}
    delta = data.get('delta')
    if not isinstance(delta, int):
        return jsonify({'msg': 'delta must be integer'}), 400
    item = WarehouseItem.query.get_or_404(item_id)
    db.session.execute(
        db.text("UPDATE warehouse_items SET quantity = quantity + :delta WHERE id = :id"),
        {'delta': delta, 'id': item_id}
    )
    db.session.commit()
    db.session.refresh(item)
    return jsonify(item.to_dict())


# @item_bp.route('/<int:item_id>/increment', methods=['POST'])
# @jwt_required()
# def increment_item_quantity(item_id):
#     """Atomically increment quantity of a warehouse item.
#     ---
#     tags:
#       - Warehouse Items
#     parameters:
#       - name: item_id
#         in: path
#         required: true
#         type: integer
#       - name: body
#         in: body
#         required: true
#         schema:
#           type: object
#           properties:
#             delta: {type: integer, description: "Amount to add (can be negative)"}
#     responses:
#       200:
#         description: Updated item with new quantity
#       404:
#         description: Not found
#     """

#     data = request.json or {}
#     delta = data.get('delta')

#     if not isinstance(delta, int):
#         return jsonify({'msg': 'delta must be integer'}), 400

#     # # Kiểm tra item tồn tại
   

#     # Append event stream thay vì update thẳng
#     event_payload = {
#         "id": item_id,
#         "delta": delta,
#     }
#     event = append_event(f"warehouse_item:{item_id}", "WarehouseItemIncremented", event_payload)

#     # Trả về kết quả mới nhất từ SQL (projection đã được apply)
#     return jsonify({
#         "event": {
#             "stream": event["stream"],
#             "version": event["version"],
#             "type": event["type"],
#             "ts": event["ts"].isoformat(),
#         },
#     })