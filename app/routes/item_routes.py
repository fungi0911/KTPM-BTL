from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required

from app.event_store.event_store import append_event, apply_events_for_stream
from ..models.warehouse_item import WarehouseItem
from ..models.product import Product
from ..models.warehouse import Warehouse
from ..extensions import db
from app.repositories import WarehouseItemRepository

item_bp = Blueprint("item", __name__, url_prefix="/warehouse_items")

# repository
item_repo = WarehouseItemRepository(db.session)

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
    # stream = f"warehouse_item"
    # apply_events_for_stream(stream)
    items = item_repo.list()

    results = []
    for i in items:
        if isinstance(i, dict):
            results.append(i)
        else:
            results.append(i.to_dict())

    return jsonify(results)

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
    rows = item_repo.product_stock_stats()
    prod_map = {p.id: p.name for p in Product.query.filter(Product.id.in_([r['product_id'] for r in rows])).all()} if rows else {}
    return jsonify([
      {'product_id': r['product_id'], 'product': prod_map.get(r['product_id']), 'total_quantity': r['total_quantity']} for r in rows
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
    rows = item_repo.warehouse_stock_stats()
    wh_map = {w.id: w.name for w in Warehouse.query.filter(Warehouse.id.in_([r['warehouse_id'] for r in rows])).all()} if rows else {}
    return jsonify([
      {'warehouse_id': r['warehouse_id'], 'warehouse': wh_map.get(r['warehouse_id']), 'total_quantity': r['total_quantity']} for r in rows
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
    item = item_repo.create(data)
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
    # stream = f"warehouse_item:{item_id}"
    # apply_events_for_stream(stream)
    item = item_repo.get_by_id(item_id)

    if not item:
      abort(404)
    
    if isinstance(item, dict):
        return jsonify(item)
    
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
    data = request.json or {}
    updated = item_repo.update(item_id, data)
    if not updated:
      abort(404)
    return jsonify(updated.to_dict())

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
    ok = item_repo.delete(item_id)
    if not ok:
      abort(404)
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
    # perform atomic update via SQL then refresh cached projection
    row = db.session.execute(
      db.text("UPDATE warehouse_items SET quantity = quantity + :delta WHERE id = :id RETURNING id"),
      {'delta': delta, 'id': item_id}
    ).fetchone()
    if not row:
      abort(404)
    db.session.commit()
    # invalidate cache for this item and stats
    from app.utils.cache import delete_key, _make_key
    delete_key(_make_key("warehouse_item", item_id))
    delete_key("warehouse_items:list")
    delete_key("stats:products")
    delete_key("stats:warehouses")
    item = item_repo.get_by_id(item_id)
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