from datetime import date, datetime
from typing import Any, Dict, Tuple

from flask import jsonify


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def success(data: Any = None, msg: str = "成功"):
    return jsonify({"code": 200, "msg": msg, "data": to_jsonable(data or {})})


def fail(msg: str = "失败", code: int = 500, data: Any = None) -> Tuple[Any, int]:
    http_status = code if code in {400, 401, 403, 404, 409} else 500
    return jsonify({"code": code, "msg": msg, "data": to_jsonable(data or {})}), http_status


def require_fields(payload: Dict[str, Any], fields: list) -> Tuple[bool, str]:
    for field in fields:
        if field not in payload or payload.get(field) in (None, ""):
            return False, field
    return True, ""


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
