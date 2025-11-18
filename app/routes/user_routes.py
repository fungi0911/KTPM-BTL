from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..models.user import User
from ..extensions import db, limiter

user_bp = Blueprint("user", __name__, url_prefix="/users")

@user_bp.route('/', methods=['GET'])
@limiter.limit("10 per minute")
@jwt_required()
def get_users():
    """Get all users
    ---
    tags:
      - Users
    responses:
      200:
        description: List of users
    """
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])

@user_bp.route('/<int:user_id>', methods=['GET'])
@limiter.limit("10 per minute")
@jwt_required()
def get_user(user_id):
    """Get user by ID
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: User object
      404:
        description: Not found
    """
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/<int:user_id>', methods=['PUT'])
@limiter.limit("10 per minute")
@jwt_required()
def update_user(user_id):
    """Update user (name, role, password)
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
      - name: body
        in: body
        schema:
          type: object
          properties:
            name: {type: string}
            role: {type: string}
            password: {type: string}
    responses:
      200:
        description: Updated user
      404:
        description: Not found
    """
    user = User.query.get_or_404(user_id)
    data = request.json or {}
    if 'name' in data:
        user.name = data['name']
    if 'role' in data:
        user.role = data['role']
    if 'password' in data:
        user.set_password(data['password'])
    db.session.commit()
    return jsonify(user.to_dict())

@user_bp.route('/<int:user_id>', methods=['DELETE'])
@limiter.limit("10 per minute")
@jwt_required()
def delete_user(user_id):
    """Delete user
    ---
    tags:
      - Users
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
    responses:
      204:
        description: Deleted successfully
      404:
        description: Not found
    """
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204


