from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..models.product import Product
from ..models.warehouse_item import WarehouseItem
from ..extensions import db

product_bp = Blueprint("product", __name__, url_prefix="/products")

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
    products = Product.query.all()
    return jsonify([p.to_dict() for p in products])

@product_bp.route('/', methods=['POST'])
@jwt_required()
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
    responses:
      201:
        description: Product created successfully
    """
    data = request.json
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
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
    product = Product.query.get_or_404(product_id)
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
    Product.query.get_or_404(product_id)
    total = db.session.execute(
        db.select(db.func.sum(WarehouseItem.quantity)).filter(WarehouseItem.product_id == product_id)
    ).scalar() or 0
    return jsonify({'product_id': product_id, 'total_quantity': int(total)})

@product_bp.route('/<int:product_id>', methods=['PUT'])
@jwt_required()
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
    product = Product.query.get_or_404(product_id)
    data = request.json or {}
    if 'name' in data:
        product.name = data['name']
    if 'price' in data:
        product.price = data['price']
    db.session.commit()
    return jsonify(product.to_dict())

@product_bp.route('/<int:product_id>', methods=['DELETE'])
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
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'status': 'deleted', 'product_id': product_id}), 200
