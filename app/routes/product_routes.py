from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..models.product import Product
from ..extensions import db

product_bp = Blueprint("product", __name__, url_prefix="/products")
@product_bp.route('/', methods=['GET'])
def get_products():
    """Get all products
    ---
    responses:
      200:
        description: List of products
    """
    products = Product.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'price': p.price} for p in products])

@product_bp.route('/', methods=['POST'])
def create_product():
    """Create a product
    ---
    parameters:
      - name: body
        in: body
        schema:
          properties:
            name: {type: string}
            price: {type: number}
    """
    data = request.json
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product created'}), 201
