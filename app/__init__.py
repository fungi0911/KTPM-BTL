from flask import Flask, request
from flasgger import Swagger
from flask_jwt_extended import verify_jwt_in_request, exceptions
from .extensions import db, jwt
from .config import Config
from .routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

    @app.before_request
    def check_jwt():
        if request.path.startswith("/apidocs") or request.path.startswith("/flasgger_static"):
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

