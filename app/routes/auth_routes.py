from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from ..models.user import User
from ..extensions import db, limiter
from ..extensions import db
from app.repositories import UserRepository

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# repository
user_repo = UserRepository(db.session)

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per minute")
def register():
    """Create a user
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        schema:
          properties:
            username: {type: string}
            name: {type: string}
            password: {type: string}
            role: {type: string}  
    responses:
      201:
        description: User created successfully  
    """
    data = request.json
    user = user_repo.create({
      'name': data['name'],
      'username': data['username'],
      'role': data.get('role', 'staff'),
      'password': data.get('password')
    })
    return jsonify(user.to_dict()), 201

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    """Login
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        schema:
          properties:
            username: {type: string}
            password: {type: string}
    responses:
      200:
        description: Login successful, returns access token
    """
    data = request.json
    user = user_repo.find_by_username(data["username"])
    if user and user.check_password(data["password"]):
      token = create_access_token(identity=user.username, additional_claims={"role": user.role})
      return jsonify({"access_token": token})
    return jsonify({"msg": "Invalid credentials"}), 401
