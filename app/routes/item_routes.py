from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required

from app.event_store.event_store import append_event, apply_events_for_stream
from ..models.warehouse_item import WarehouseItem
from ..models.product import Product
from ..models.warehouse import Warehouse
from ..extensions import db, limiter
from app.repositories import WarehouseItemRepository
from app.utils.occ import occ_execute
from requests.exceptions import RequestException
from ..services.resilience import CircuitOpenError, RetryExhaustedError
from ..services.vendor_api import UpstreamClientError, get_vendor_client
from app.repositories import ProductRepository
from app.tasks import update_product_price

item_bp = Blueprint("item", __name__, url_prefix="/warehouse_items")

# repository
item_repo = WarehouseItemRepository(db.session)
product_repo = ProductRepository(db.session)


@item_bp.route('/', methods=['GET'])
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
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
            version: {type: integer}
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
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
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
            version: {type: integer, description: "Expected current version for OCC (optional)"}
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
    # Naive mode (no OCC) for demo/testing lost updates: ?mode=naive
    mode = request.args.get('mode')
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
      }), 200

    # Generic OCC executor: routes define SQL builder, OCC handles retries
    read_sql = "SELECT COALESCE(version, 0) AS version FROM warehouse_items WHERE id = :id"
    read_params = {'id': item_id}

    client_version = data.get('version') if isinstance(data.get('version'), int) else None

    def build_update(expected_version: int):
      update_sql = """
        UPDATE warehouse_items
        SET quantity = quantity + :delta, version = :new_version
        WHERE id = :id AND (version = :expected_version OR version IS NULL)
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
    }), 200


@item_bp.route('/transfer', methods=['POST'])
@jwt_required()
def transfer_items():
    """
    Atomic multi-item quantity transfer with optimistic concurrency control (OCC).
    ---
    tags:
      - Warehouse Items
    summary: Atomically transfer quantities between multiple warehouse items
    description: |
      Applies a list of increment/decrement operations on warehouse items atomically.
      Any underflow or conflict aborts the transfer. Supports OCC (version-based).
      Caches and aggregates will be invalidated for affected items.

    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - operations
          properties:
            operations:
              type: array
              description: List of operations to apply
              items:
                type: object
                required:
                  - item_id
                  - delta
                properties:
                  item_id:
                    type: integer
                    description: ID of the warehouse item
                  delta:
                    type: integer
                    description: Amount to add (can be negative)
                  version:
                    type: integer
                    description: Optional expected current version for OCC of this item
              example:
                - item_id: 1
                  delta: -5
                - item_id: 2
                  delta: 5
                - item_id: 3
                  delta: -2
                - item_id: 4
                  delta: 2

    responses:
      200:
        description: Transfer succeeded; returns updated warehouse items
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            updated:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  quantity:
                    type: integer
                  version:
                    type: integer
                  product_id:
                    type: integer
                  warehouse_id:
                    type: integer
      400:
        description: Bad request; e.g., missing operations or no effective changes
      404:
        description: Some item IDs were not found
      409:
        description: Conflict or underflow; transfer aborted
      500:
        description: Internal server error during transfer
    """
    payload = request.json or {}
    ops = payload.get('operations')
    if not isinstance(ops, list) or not ops:
      return jsonify({'msg': 'operations must be a non-empty list'}), 400

    # Aggregate deltas per item and deduplicate same-row updates
    agg: dict[int, int] = {}
    for op in ops:
      if not isinstance(op, dict):
        return jsonify({'msg': 'each operation must be an object'}), 400
      item_id = op.get('item_id')
      delta = op.get('delta')
      if not isinstance(item_id, int) or not isinstance(delta, int):
        return jsonify({'msg': 'item_id and delta must be integers'}), 400
      agg[item_id] = agg.get(item_id, 0) + delta

    # Build final operations excluding zero net changes
    norm_ops = [{'id': i, 'delta': d} for i, d in agg.items() if d != 0]
    if not norm_ops:
      return jsonify({'msg': 'no effective operations'}), 400

    # Execute all OCC updates within a single transaction using occ_execute(commit=False)
    try:
      # Apply OCC per item without auto-commit; commit once if all succeed.
      # No pessimistic locks; enforce quantity guard inside UPDATE when decrementing.
      for op in norm_ops:
        read_sql = "SELECT COALESCE(version, 0) AS version FROM warehouse_items WHERE id = :id"
        read_params = {'id': op['id']}
        def build_update(expected_version: int, _op=op):
          if _op['delta'] < 0:
            update_sql = """
              UPDATE warehouse_items
              SET quantity = quantity + :delta, version = :new_version
              WHERE id = :id
                AND (version = :expected_version OR version IS NULL)
                AND quantity >= :need_qty
            """
            update_params = {
              'id': _op['id'],
              'delta': _op['delta'],
              'expected_version': expected_version,
              'new_version': expected_version + 1,
              'need_qty': -_op['delta'],
            }
          else:
            update_sql = """
              UPDATE warehouse_items
              SET quantity = quantity + :delta, version = :new_version
              WHERE id = :id AND (version = :expected_version OR version IS NULL)
            """
            update_params = {
              'id': _op['id'],
              'delta': _op['delta'],
              'expected_version': expected_version,
              'new_version': expected_version + 1,
            }
          return update_sql, update_params
        client_version = None
        # Accept optional version from original payload op entries
        # Map original ops list to find version if provided (single pass acceptable given small size)
        # Simpler: recompute from payload ops list
        for original in ops:
          if isinstance(original, dict) and original.get('item_id') == op['id'] and isinstance(original.get('version'), int):
            client_version = original.get('version')
            break
        ok = occ_execute(
          read_sql,
          read_params,
          build_update,
          session=db.session,
          commit=False,
          expected_version_override=client_version
        )
        if not ok:
          db.session.rollback()
          return jsonify({'msg': 'conflict, transfer aborted'}), 409
      db.session.commit()
    except Exception as e:
      db.session.rollback()
      return jsonify({'msg': 'transfer failed', 'error': str(e)}), 500

    # Invalidate caches for affected items & aggregates
    from app.utils.cache import delete_key, _make_key
    delete_key('warehouse_items:list')
    delete_key('stats:products')
    delete_key('stats:warehouses')
    for op in norm_ops:
      delete_key(_make_key('warehouse_item', op['id']))

    # Return fresh states
    ids = [op['id'] for op in norm_ops]
    rows = db.session.execute(
      db.text(f"SELECT id, quantity, version, product_id, warehouse_id FROM warehouse_items WHERE id IN ({','.join(str(i) for i in ids)})")
    ).mappings().all()
    return jsonify({
      'status': 'ok',
      'updated': [dict(r) for r in rows]
    }), 200

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
#     from app.utils.cache import delete_key, _make_key
#     delete_key(_make_key("warehouse_item", item_id))
#     delete_key("warehouse_items:list")
#     delete_key("stats:products")
#     delete_key("stats:warehouses")

#     # Trả về kết quả mới nhất từ SQL (projection đã được apply)
#     return jsonify({
#         "event": {
#             "stream": event["stream"],
#             "version": event["version"],
#             "type": event["type"],
#             "ts": event["ts"].isoformat(),
#         },
#     })

@item_bp.route('/vendor_price/<int:product_id>', methods=['GET'])
def get_vendor_price(product_id: int):
    """Fetch current vendor price for a product via ACL (Circuit Breaker + Retry)
    ---
    tags:
      - Warehouse Items
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
      - name: mode
        in: query
        type: string
        enum: [down, flaky, ok]
        description: Mock vendor behavior mode
      - name: strategy
        in: query
        type: string
        enum: [resilient, raw]
        description: Use 'raw' to bypass resilience
      - name: fail_rate
        in: query
        type: number
        description: Failure rate for flaky mode
      - name: delay_ms
        in: query
        type: integer
        description: Artificial delay in ms
    responses:
      200:
        description: Vendor price payload with metadata
      400:
        description: Client error (non-retryable)
      502:
        description: Vendor error after retries
      503:
        description: Circuit open
    """
    client = get_vendor_client()
    strategy = request.args.get("strategy", "resilient")
    
    # Pass mock control params to vendor
    passthrough = {
        k: v for k, v in request.args.items() 
        if k in {"mode", "fail_rate", "delay_ms"}
    }
    
    try:
        if strategy == "raw":
            data, attempts = client.get_price_raw(
                product_id, 
                params=passthrough or None
            )
        else:
            data, attempts = client.get_price(
                product_id, 
                params=passthrough or None
            )
        update_task_id = None
        update_status = "skipped"
        if isinstance(data, dict) and "price" in data:
            product = product_repo.get_by_id(product_id)
            if product:
                task = update_product_price.delay(product_id, data["price"])
                update_task_id = task.id
                update_status = "enqueued"
            else:
                update_status = "product_not_found"

        return jsonify({
            "data": data,
            "attempts": attempts,
            "strategy": strategy,
            "state": client.snapshot(),
            "price_update": {
                "status": update_status,
                "task_id": update_task_id,
            }
        })
    
    except CircuitOpenError as e:
        return jsonify({
            "msg": "Circuit open: vendor temporarily disabled",
            "breaker_name": e.breaker_name,
            "state": e.breaker_state,
        }), 503
    
    except UpstreamClientError as e:
        return jsonify({
            "msg": "Vendor client error (non-retryable)",
            "status": e.status_code,
            "detail": e.payload,
            "state": client.snapshot(),
        }), e.status_code
    
    except RetryExhaustedError as e:
        return jsonify({
            "msg": "Vendor error after retries",
            "attempts": e.attempts,
            "last_error": str(e.last_exception),
            "state": client.snapshot(),
        }), 502
    
    except RequestException as e:
        # Should only happen in raw mode
        return jsonify({
            "msg": "Network error (no resilience)",
            "detail": str(e),
            "state": client.snapshot(),
        }), 502


@item_bp.route('/vendor_state', methods=['GET'])
def get_vendor_state():
    """Expose circuit breaker state and metrics.
    ---
    tags:
      - Warehouse Items
    responses:
      200:
        description: Current vendor client state
    """
    client = get_vendor_client()
    return jsonify(client.snapshot())
