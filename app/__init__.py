from flask import Flask, request
from flasgger import Swagger
from flask_jwt_extended import verify_jwt_in_request, exceptions
from .extensions import db, jwt, mongo_client
from .config import Config
from .routes import register_routes
from app.event_store import event_store

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    jwt.init_app(app)

    global mongo_client
    if mongo_client is None:
        from pymongo import MongoClient
        mongo_client = MongoClient(app.config.get("MONGO_URI"))
 
        mongo_client.admin.command('ping')
        event_store.mongo_client = mongo_client
        event_store.init_event_store()

    @app.before_request
    def check_jwt():
        allowed_paths = [
            "/apidocs",
            "/flasgger_static",
            "/apispec_1.json",
            "/auth/login",
            "/auth/register"
        ]
        if any(request.path.startswith(p) for p in allowed_paths):
            return
        try:
            verify_jwt_in_request()
        except exceptions.NoAuthorizationError:
            return {"msg": "Missing or invalid token"}, 401


    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Inventory API",
            "description": "API documentation for the Inventory system",
            "version": "1.0.0"
        },
        # Tag groups for clearer grouping in Swagger UI
        "tags": [
            {"name": "Auth", "description": "Authentication & token issuance"},
            {"name": "Users", "description": "User management"},
            {"name": "Products", "description": "Product catalog operations"},
            {"name": "Warehouses", "description": "Warehouse management"},
            {"name": "Warehouse Items", "description": "Inventory items in warehouses"},
        ],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: 'Authorization: Bearer {token}'"
            }
        },
        "security": [{"Bearer": []}],
    }

    Swagger(app, template=swagger_template)

    # --- Đăng ký routes ---
    register_routes(app)

    return app

