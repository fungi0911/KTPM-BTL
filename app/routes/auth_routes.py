from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from ..models.user import User
from ..extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["POST"])
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
    user = User(
        name=data["name"],
        username=data["username"],
        role=data.get("role", "staff")
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@auth_bp.route("/login", methods=["POST"])
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
    user = User.query.filter_by(username=data["username"]).first()
    if user and user.check_password(data["password"]):
        token = create_access_token(identity=user.username, additional_claims={"role": user.role})
        return jsonify({"access_token": token})
    return jsonify({"msg": "Invalid credentials"}), 401
