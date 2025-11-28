from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from app.utils.rbac import roles_required
from ..extensions import db
from app.repositories import UserRepository

user_bp = Blueprint("user", __name__, url_prefix="/users")

# repository
user_repo = UserRepository(db.session)

@user_bp.route('/', methods=['GET'])
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
    users = user_repo.list()
    return jsonify([u.to_dict() for u in users])

@user_bp.route('/<int:user_id>', methods=['GET'])
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
    user = user_repo.get_by_id(user_id)
    if not user:
      abort(404)
    return jsonify(user.to_dict())

@user_bp.route('/<int:user_id>', methods=['PUT'])
@roles_required(['admin'])
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
    data = request.json or {}
    updated = user_repo.update(user_id, data)
    if not updated:
      abort(404)
    return jsonify(updated.to_dict())

@user_bp.route('/<int:user_id>', methods=['DELETE'])
@roles_required(['admin'])
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
    ok = user_repo.delete(user_id)
    if not ok:
      abort(404)
    return jsonify({'status': 'deleted', 'user_id': user_id}), 200


