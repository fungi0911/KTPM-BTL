from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt


def roles_required(allowed_roles):
    if isinstance(allowed_roles, str):
        allowed = {allowed_roles}
    else:
        allowed = set(allowed_roles or [])

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt() or {}
            role = claims.get("role")
            if role not in allowed:
                return jsonify({"msg": "forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
