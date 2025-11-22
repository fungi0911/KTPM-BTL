from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from ..extensions import db
from app.repositories import WarehouseRepository

warehouse_bp = Blueprint("warehouse", __name__, url_prefix="/warehouses")

# repository
warehouse_repo = WarehouseRepository(db.session)

@warehouse_bp.route('/', methods=['GET'])
def get_warehouses():
    """Get all warehouses
    ---
    tags:
      - Warehouses
    responses:
      200:
        description: List of warehouses
    """
    warehouses = warehouse_repo.list()
    return jsonify([w.to_dict() for w in warehouses])

@warehouse_bp.route('/', methods=['POST'])
@jwt_required()
def create_warehouse():
    """Create a new warehouse
    ---
    tags:
      - Warehouses
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string}
    responses:
      201:
        description: Warehouse created successfully
    """
    data = request.json
    warehouse = warehouse_repo.create(data)
    return jsonify(warehouse.to_dict()), 201

@warehouse_bp.route('/<int:warehouse_id>', methods=['GET'])
def get_warehouse(warehouse_id):
    """Get warehouse by ID
    ---
    tags:
      - Warehouses
    parameters:
      - name: warehouse_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Warehouse object
      404:
        description: Not found
    """
    w = warehouse_repo.get_by_id(warehouse_id)
    if not w:
      abort(404)
    return jsonify(w.to_dict())

@warehouse_bp.route('/<int:warehouse_id>/items', methods=['GET'])
def get_items_for_warehouse(warehouse_id):
    """List items in a specific warehouse with optional product filter
    ---
    tags:
      - Warehouses
    parameters:
      - name: warehouse_id
        in: path
        required: true
        type: integer
      - name: product_id
        in: query
        type: integer
    responses:
      200:
        description: Items stored in warehouse
      404:
        description: Warehouse not found
    """
    # ensure exists
    if not warehouse_repo.get_by_id(warehouse_id):
      abort(404)
    product_id = request.args.get('product_id', type=int)
    items = warehouse_repo.get_items_for_warehouse(warehouse_id, product_id)
    return jsonify([i.to_dict() for i in items])

@warehouse_bp.route('/<int:warehouse_id>', methods=['PUT'])
@jwt_required()
def update_warehouse(warehouse_id):
    """Update warehouse
    ---
    tags:
      - Warehouses
    parameters:
      - name: warehouse_id
        in: path
        required: true
        type: integer
      - name: body
        in: body
        schema:
          type: object
          properties:
            name: {type: string}
    responses:
      200:
        description: Updated warehouse
      404:
        description: Not found
    """
    data = request.json or {}
    updated = warehouse_repo.update(warehouse_id, data)
    if not updated:
      abort(404)
    return jsonify(updated.to_dict())

@warehouse_bp.route('/<int:warehouse_id>', methods=['DELETE'])
@jwt_required()
def delete_warehouse(warehouse_id):
    """Delete warehouse
    ---
    tags:
      - Warehouses
    parameters:
      - name: warehouse_id
        in: path
        required: true
        type: integer
    responses:
      204:
        description: Deleted successfully
      404:
        description: Not found
    """
    ok = warehouse_repo.delete(warehouse_id)
    if not ok:
      abort(404)
    return jsonify({'status': 'deleted', 'warehouse_id': warehouse_id}), 200
