import json
from typing import Any
import app.extensions as extensions

DEFAULT_TTL = 300  # seconds

 # Sử dụng extensions.redis_client từ extensions

def _make_key(prefix: str, *parts) -> str:
    if not parts:
        return prefix
    return prefix + ":" + ":".join(str(p) for p in parts)

def get_json(key: str) -> Any:
    if extensions.redis_client is None:
        return None
    try:
        raw = extensions.redis_client.get(key)
        print(f"🔍 Đang truy xuất khóa {key} từ Redis")  # Log khi truy xuất
    except Exception:
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None

def set_json(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    if extensions.redis_client is None:
        return
    try:
        extensions.redis_client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        print(f"💾 [SAVE] Đã lưu khóa {key} vào Redis với TTL {ttl} giây")  # Log khi lưu
    except Exception as e:
        print(f"❌ LỖI TRONG SET_JSON: {e}")
        return

def delete_key(key: str) -> None:
    if extensions.redis_client is None:
        return
    try:
        extensions.redis_client.delete(key)
    except Exception:
        return
