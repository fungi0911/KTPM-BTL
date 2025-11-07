from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..models.warehouse_item import WarehouseItem
from ..extensions import db

item_bp = Blueprint("item", __name__, url_prefix="/warehouse_items")

@item_bp.route('/', methods=['GET'])
def get_warehouse_items():
    """Get all warehouse items
    ---
    responses:
      200:
        description: List of warehouse items with warehouse & product info
    """
    items = WarehouseItem.query.all()
    return jsonify([
        {
            'id': i.id,
            'warehouse': i.warehouse.name,
            'product': i.product.name,
            'quantity': i.quantity
        } for i in items
    ])

@item_bp.route('/', methods=['POST'])
def create_warehouse_item():
    """Add product to warehouse
    ---
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
    return jsonify({'message': 'Warehouse item created'}), 201
