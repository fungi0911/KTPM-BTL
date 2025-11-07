from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..models.warehouse import Warehouse
from ..extensions import db

warehouse_bp = Blueprint("warehouse", __name__, url_prefix="/warehouses")

@warehouse_bp.route('/', methods=['GET'])
def get_warehouses():
    """Get all warehouses
    ---
    responses:
      200:
        description: List of warehouses
    """
    warehouses = Warehouse.query.all()
    return jsonify([{'id': w.id, 'name': w.name} for w in warehouses])

@warehouse_bp.route('/', methods=['POST'])
def create_warehouse():
    """Create a new warehouse
    ---
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
    return jsonify({'message': 'Warehouse created'}), 201
