from flask import Flask, request
from flasgger import Swagger
from flask_jwt_extended import verify_jwt_in_request, exceptions
from flask_limiter import RateLimitExceeded

from .celery_app import init_celery
from .extensions import db, jwt, limiter
from .config import Config
from .routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    limiter.init_app(app)

    init_celery(app)

    db.init_app(app)
    jwt.init_app(app)

    @app.before_request
    def check_jwt():
        allowed_paths = [
            "/apidocs",
            "/flasgger_static",
            "/apispec_1.json",
            "/auth/login",
            "/auth/register",
            "/export"
        ]
        if any(request.path.startswith(p) for p in allowed_paths):
            return
        try:
            verify_jwt_in_request()
        except exceptions.NoAuthorizationError:
            return {"msg": "Missing or invalid token"}, 401

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return {
            "error": "Rate limit exceeded",
            "message": str(e)  # Thông tin chi tiết
        }, 429

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
            {"name": "Export", "description": "Export management"},
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

