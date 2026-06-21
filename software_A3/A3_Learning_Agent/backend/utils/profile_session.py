from typing import Optional

from flask import request

from db import mysql_db


def profile_session_id_from_payload(payload: Optional[dict] = None):
    payload = payload or {}
    raw = payload.get("profile_session_id") or request.args.get("profile_session_id")
    if raw in (None, "", "null", "undefined"):
        return None
    try:
        return int(raw)
    except Exception:
        return None


def session_belongs_to_user(user_id: int, session_id: int) -> bool:
    return bool(mysql_db.query_one("SELECT id FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id)))


def set_active_profile_session(user_id: int, session_id: int) -> None:
    mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    mysql_db.update("profile_session", {"is_active": 1}, "id=%s AND user_id=%s", (session_id, user_id))


def create_profile_session(user_id: int, title: Optional[str] = None, activate: bool = True) -> dict:
    existing_count = mysql_db.query_one("SELECT COUNT(*) AS total FROM profile_session WHERE user_id=%s", (user_id,)) or {}
    default_title = title or f"画像对话 {int(existing_count.get('total') or 0) + 1}"
    if activate:
        mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    session_id = mysql_db.insert("profile_session", {"user_id": user_id, "title": default_title, "is_active": 1 if activate else 0})
    return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s", (session_id,))


def active_profile_session(user_id: int, create_if_missing: bool = False):
    row = mysql_db.query_one("SELECT * FROM profile_session WHERE user_id=%s AND is_active=1 ORDER BY update_time DESC LIMIT 1", (user_id,))
    if row:
        return row
    row = mysql_db.query_one("SELECT * FROM profile_session WHERE user_id=%s ORDER BY update_time DESC LIMIT 1", (user_id,))
    if row:
        set_active_profile_session(user_id, row["id"])
        row["is_active"] = 1
        return row
    if create_if_missing:
        return create_profile_session(user_id, activate=True)
    return None


def resolve_profile_session(user_id: int, payload: Optional[dict] = None, create_if_missing: bool = False):
    session_id = profile_session_id_from_payload(payload)
    if session_id is not None:
        if not session_belongs_to_user(user_id, session_id):
            return None
        return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id))
    return active_profile_session(user_id, create_if_missing=create_if_missing)
