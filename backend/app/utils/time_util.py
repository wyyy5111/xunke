"""通用工具：JSON 序列化、时间。"""
import json
from datetime import datetime, timezone


def now_ms() -> int:
    from time import time
    return int(time() * 1000)


def utc_now() -> datetime:
    """Return naive UTC for existing SQLAlchemy DateTime columns without utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def safe_json_loads(s: str, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def safe_json_dumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return "{}"
