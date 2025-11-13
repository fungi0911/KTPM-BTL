from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..models.warehouse import Warehouse
from ..models.warehouse_item import WarehouseItem
from ..extensions import db

warehouse_bp = Blueprint("warehouse", __name__, url_prefix="/warehouses")

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
    warehouses = Warehouse.query.all()
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
    warehouse = Warehouse(**data)
    db.session.add(warehouse)
    db.session.commit()
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
    w = Warehouse.query.get_or_404(warehouse_id)
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
    Warehouse.query.get_or_404(warehouse_id)
    product_id = request.args.get('product_id', type=int)
    q = WarehouseItem.query.filter(WarehouseItem.warehouse_id == warehouse_id)
    if product_id:
        q = q.filter(WarehouseItem.product_id == product_id)
    items = q.all()
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
    w = Warehouse.query.get_or_404(warehouse_id)
    data = request.json or {}
    if 'name' in data:
        w.name = data['name']
    db.session.commit()
    return jsonify(w.to_dict())

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
    w = Warehouse.query.get_or_404(warehouse_id)
    db.session.delete(w)
    db.session.commit()
    return jsonify({'status': 'deleted', 'warehouse_id': warehouse_id}), 200
