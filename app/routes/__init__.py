from .auth_routes import auth_bp
from .product_routes import product_bp
from .warehouse_routes import warehouse_bp
from .item_routes import item_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(item_bp)
