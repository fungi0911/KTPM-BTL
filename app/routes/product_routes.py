from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from app.utils.rbac import roles_required
from ..extensions import db
from ..models.product import Product
from ..models.warehouse_item import WarehouseItem
from ..extensions import db, limiter
from app.repositories import ProductRepository

product_bp = Blueprint("product", __name__, url_prefix="/products")

# instantiate repository (uses app-wide db.session by default)
product_repo = ProductRepository(db.session)

@product_bp.route('/', methods=['GET'])
def get_products():
    """Get all products
    ---
    tags:
      - Products
    responses:
      200:
        description: List of products
    """
    products = product_repo.list()
    return jsonify([p.to_dict() for p in products])

@product_bp.route('/', methods=['POST'])
@jwt_required()
@roles_required(['admin'])
def create_product():
    """Create a product
    ---
    tags:
      - Products
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string}
            price: {type: number}
            version: {type: integer}
    responses:
      201:
        description: Product created successfully
    """
    data = request.json
    product = product_repo.create(data)
    return jsonify(product.to_dict()), 201

@product_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get product by ID
    ---
    tags:
      - Products
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Product object
      404:
        description: Not found
    """
    product = product_repo.get_by_id(product_id)
    if not product:
      abort(404)
    return jsonify(product.to_dict())

@product_bp.route('/<int:product_id>/stock', methods=['GET'])
def get_product_stock(product_id):
    """Get total stock of a product across all warehouses
    ---
    tags:
      - Products
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Total quantity summary
      404:
        description: Product not found
    """
    # ensure product exists
    if not product_repo.get_by_id(product_id):
      abort(404)
    total = product_repo.get_stock(product_id)
    return jsonify({'product_id': product_id, 'total_quantity': int(total)})

@product_bp.route('/<int:product_id>', methods=['PUT'])
@jwt_required()
@roles_required(['admin'])
def update_product(product_id):
    """Update a product
    ---
    tags:
      - Products
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
      - name: body
        in: body
        schema:
          type: object
          properties:
            name: {type: string}
            price: {type: number}
    responses:
      200:
        description: Updated product
      404:
        description: Not found
    """
    data = request.json or {}
    updated = product_repo.update(product_id, data)
    if not updated:
      abort(404)
    return jsonify(updated.to_dict())

@product_bp.route('/<int:product_id>', methods=['DELETE'])
@roles_required(['admin'])
@jwt_required()
def delete_product(product_id):
    """Delete product
    ---
    tags:
      - Products
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
    responses:
      204:
        description: Deleted successfully
      404:
        description: Not found
    """
    ok = product_repo.delete(product_id)
    if not ok:
      abort(404)
    return jsonify({'status': 'deleted', 'product_id': product_id}), 200
