import json
from typing import Any
from app.extensions import redis_client

DEFAULT_TTL = 300  # seconds

def _make_key(prefix: str, *parts) -> str:
    if not parts:
        return prefix
    return prefix + ":" + ":".join(str(p) for p in parts)

def get_json(key: str) -> Any:
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(key)
    except Exception:
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None

def set_json(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    if redis_client is None:
        return
    try:
        redis_client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception:
        return

def delete_key(key: str) -> None:
    if redis_client is None:
        return
    try:
        redis_client.delete(key)
    except Exception:
        return
