from flask import Flask, request, g, json
import time
from flasgger import Swagger
from flask_jwt_extended import verify_jwt_in_request, exceptions
from pymongo import MongoClient
from .extensions import db, jwt, mongo_client, redis_client
from redis import Redis
from .config import Config
from .routes import register_routes
from app.event_store import event_store

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    jwt.init_app(app)
    # SQLAlchemy query-counter instrumentation has been removed per user request.

    #Đoạn này để khởi tạo kết nối MongoDB cho event store, xoá đi không nó không chạy được
    global mongo_client
    if mongo_client is None:
        try:
            mongo_client = MongoClient(app.config.get("MONGO_URI"))
            mongo_client.admin.command('ping')
            event_store.mongo_client = mongo_client
            event_store.init_event_store()
            print("Connected to MongoDB for event store")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")

    # Initialize Redis client for caching
    global redis_client
    if redis_client is None:
        try:
            redis_client = Redis.from_url(app.config.get("REDIS_URL"))
            redis_client.ping()
            print("Connected to Redis for caching")
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")

    @app.before_request
    def start_and_check_jwt():
        # Start timer for response time measurement
        g._rt_start = time.perf_counter()
        # request timer start
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

    @app.after_request
    def add_response_time(resp):
        # Skip swagger UI and static
        if request.path.startswith('/apidocs') or request.path.startswith('/flasgger_static'):
            return resp
        try:
            start = getattr(g, '_rt_start', None)
            if start is None:
                return resp
            content_type = resp.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                return resp
            if resp.status_code == 204:
                return resp
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            parsed = resp.get_json(silent=True)
            # Wrap non-dict JSON (list, number, string, None)
            if isinstance(parsed, dict):
                envelope = parsed
            else:
                envelope = {'data': parsed}
            if 'response_time_ms' not in envelope:
                envelope['response_time_ms'] = round(elapsed_ms, 2)
            # include DB query count if available
            envelope['db_queries'] = int(getattr(g, 'qcount', 0))
            resp.set_data(json.dumps(envelope, ensure_ascii=False))
            resp.headers['Content-Type'] = 'application/json'
            return resp
        except Exception:
            return resp


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

