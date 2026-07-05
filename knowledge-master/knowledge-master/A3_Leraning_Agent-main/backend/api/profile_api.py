import json

from flask import Blueprint, request

from ai.agents import ProfileAgent
from ai.spark_api import content_audit
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

profile_bp = Blueprint("profile", __name__)
profile_agent = ProfileAgent()

PROFILE_FIELDS = [
    "major",
    "target_course",
    "knowledge_level",
    "study_style",
    "weak_points",
    "study_goal",
    "study_time_prefer",
    "course_progress",
    "challenge_scene",
    "preferred_resource",
    "profile_summary",
]

DEFAULT_VALUE = "待进一步观察"


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _profile_session_id_from_payload(payload: dict | None = None):
    payload = payload or {}
    raw = payload.get("profile_session_id") or request.args.get("profile_session_id")
    if raw in (None, "", "null", "undefined"):
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _session_belongs_to_user(user_id: int, session_id: int) -> bool:
    return bool(mysql_db.query_one("SELECT id FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id)))


def _set_active_session(user_id: int, session_id: int) -> None:
    mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    mysql_db.update("profile_session", {"is_active": 1}, "id=%s AND user_id=%s", (session_id, user_id))


def _create_session(user_id: int, title: str | None = None, activate: bool = True) -> dict:
    existing_count = mysql_db.query_one("SELECT COUNT(*) AS total FROM profile_session WHERE user_id=%s", (user_id,)) or {}
    default_title = title or f"画像对话 {int(existing_count.get('total') or 0) + 1}"
    if activate:
        mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    session_id = mysql_db.insert(
        "profile_session",
        {"user_id": user_id, "title": default_title, "is_active": 1 if activate else 0},
    )
    return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s", (session_id,))


def _active_session(user_id: int, create_if_missing: bool = False):
    row = mysql_db.query_one(
        "SELECT * FROM profile_session WHERE user_id=%s AND is_active=1 ORDER BY update_time DESC LIMIT 1",
        (user_id,),
    )
    if row:
        return row
    row = mysql_db.query_one(
        "SELECT * FROM profile_session WHERE user_id=%s ORDER BY update_time DESC LIMIT 1",
        (user_id,),
    )
    if row:
        _set_active_session(user_id, row["id"])
        row["is_active"] = 1
        return row
    if create_if_missing:
        return _create_session(user_id, activate=True)
    return None


def _resolve_session(user_id: int, payload: dict | None = None, create_if_missing: bool = False):
    session_id = _profile_session_id_from_payload(payload)
    if session_id is not None:
        if not _session_belongs_to_user(user_id, session_id):
            return None
        return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id))
    return _active_session(user_id, create_if_missing=create_if_missing)


def _empty_profile(session_id=None):
    data = {"profile_session_id": session_id}
    data.update({field: "" for field in PROFILE_FIELDS})
    return data


def _delete_session_outputs(user_id: int, session_id: int) -> None:
    resources = mysql_db.query_all(
        "SELECT id FROM study_resource WHERE user_id=%s AND profile_session_id=%s",
        (user_id, session_id),
    )
    for item in resources:
        mysql_db.delete("resource_source", "resource_id=%s", (item["id"],))
    mysql_db.delete("study_resource", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("study_path", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("generation_batch", "user_id=%s AND profile_session_id=%s", (user_id, session_id))


@profile_bp.get("/sessions")
@login_required
def list_sessions():
    try:
        session = _active_session(request.user_id, create_if_missing=True)
        rows = mysql_db.query_all(
            """
            SELECT ps.*,
                   sp.profile_summary,
                   sp.major,
                   sp.target_course,
                   sp.update_time AS profile_update_time
            FROM profile_session ps
            LEFT JOIN student_profile sp
              ON sp.user_id = ps.user_id AND sp.profile_session_id = ps.id
            WHERE ps.user_id=%s
            ORDER BY ps.is_active DESC, ps.update_time DESC, ps.id DESC
            """,
            (request.user_id,),
        )
        return success({"sessions": rows, "active_session_id": session["id"] if session else None}, "查询成功")
    except Exception as exc:
        return fail("画像会话查询失败", 500, {"error": str(exc)})


@profile_bp.post("/sessions")
@login_required
def create_session():
    try:
        payload = request.get_json(silent=True) or {}
        session = _create_session(request.user_id, payload.get("title"), activate=True)
        return success(session, "画像对话已新建")
    except Exception as exc:
        return fail("画像对话新建失败", 500, {"error": str(exc)})


@profile_bp.post("/sessions/<int:session_id>/activate")
@login_required
def activate_session(session_id: int):
    try:
        if not _session_belongs_to_user(request.user_id, session_id):
            return fail("画像会话不存在", 404)
        _set_active_session(request.user_id, session_id)
        return success({"profile_session_id": session_id}, "画像会话已切换")
    except Exception as exc:
        return fail("画像会话切换失败", 500, {"error": str(exc)})


@profile_bp.post("/sessions/<int:session_id>/reset")
@login_required
def reset_session(session_id: int):
    try:
        if not _session_belongs_to_user(request.user_id, session_id):
            return fail("画像会话不存在", 404)
        mysql_db.delete("student_profile", "user_id=%s AND profile_session_id=%s", (request.user_id, session_id))
        mysql_db.delete("profile_conversation", "user_id=%s AND profile_session_id=%s", (request.user_id, session_id))
        _delete_session_outputs(request.user_id, session_id)
        _set_active_session(request.user_id, session_id)
        return success({"profile_session_id": session_id, "profile": _empty_profile(session_id)}, "画像会话已清空")
    except Exception as exc:
        return fail("画像会话清空失败", 500, {"error": str(exc)})


@profile_bp.post("/create")
@login_required
def create_profile():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["dialogue"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        session_id = session["id"]
        _set_active_session(request.user_id, session_id)

        dialogue = str(payload["dialogue"])
        if not content_audit(dialogue):
            return fail("学生对话未通过内容审核", 403)

        profile = profile_agent.analyze(dialogue)
        data = {
            "user_id": request.user_id,
            "profile_session_id": session_id,
            **{field: profile.get(field, DEFAULT_VALUE) for field in PROFILE_FIELDS},
        }
        mysql_db.upsert_by_unique_key(
            "student_profile",
            data,
            update_fields=["profile_session_id", *PROFILE_FIELDS],
        )
        title = data.get("profile_summary") or data.get("target_course") or data.get("major") or session.get("title")
        mysql_db.update("profile_session", {"title": str(title)[:120]}, "id=%s AND user_id=%s", (session_id, request.user_id))

        conversation = payload.get("conversation")
        if isinstance(conversation, dict):
            _save_conversation_payload(request.user_id, session_id, conversation)

        _delete_session_outputs(request.user_id, session_id)
        return success(data, "画像创建成功")
    except Exception as exc:
        return fail("画像创建失败", 500, {"error": str(exc)})


@profile_bp.post("/update")
@login_required
def update_profile():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["learning_data"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        session_id = session["id"]

        learning_data = str(payload["learning_data"])
        if not content_audit(learning_data):
            return fail("学习数据未通过内容审核", 403)

        old_profile = mysql_db.query_one(
            "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session_id),
        ) or {}
        dialogue = f"历史画像：{old_profile}\n最新学习数据：{learning_data}"
        profile = profile_agent.analyze(dialogue)
        data = {field: profile.get(field, DEFAULT_VALUE) for field in PROFILE_FIELDS}
        affected = mysql_db.update(
            "student_profile",
            data,
            "user_id=%s AND profile_session_id=%s",
            (request.user_id, session_id),
        )
        if affected == 0:
            mysql_db.insert("student_profile", {"user_id": request.user_id, "profile_session_id": session_id, **data})
        _delete_session_outputs(request.user_id, session_id)
        return success({"user_id": request.user_id, "profile_session_id": session_id, **data}, "画像更新成功")
    except Exception as exc:
        return fail("画像更新失败", 500, {"error": str(exc)})


@profile_bp.get("/")
@login_required
def get_my_profile():
    try:
        session = _resolve_session(request.user_id, create_if_missing=False)
        if not session:
            return success(_empty_profile(), "暂无画像")
        profile = mysql_db.query_one(
            "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session["id"]),
        )
        return success(profile or _empty_profile(session["id"]), "查询成功")
    except Exception as exc:
        return fail("画像查询失败", 500, {"error": str(exc)})


@profile_bp.get("/<int:user_id>")
@login_required
def get_profile(user_id: int):
    return get_my_profile()


def _save_conversation_payload(user_id: int, session_id: int, payload: dict) -> None:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    answer_map = payload.get("answer_map") if isinstance(payload.get("answer_map"), dict) else {}
    extra_notes = payload.get("extra_notes") if isinstance(payload.get("extra_notes"), list) else []
    current_index = int(payload.get("current_index") or 0)
    data = {
        "user_id": user_id,
        "profile_session_id": session_id,
        "messages": _json_dumps(messages),
        "answer_map": _json_dumps(answer_map),
        "extra_notes": _json_dumps(extra_notes),
        "current_index": current_index,
    }
    mysql_db.upsert_by_unique_key(
        "profile_conversation",
        data,
        update_fields=["messages", "answer_map", "extra_notes", "current_index"],
    )


@profile_bp.get("/conversation")
@login_required
def get_conversation():
    try:
        session = _resolve_session(request.user_id, create_if_missing=False)
        if not session:
            return success({}, "暂无对话记录")
        row = mysql_db.query_one(
            "SELECT * FROM profile_conversation WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session["id"]),
        )
        if not row:
            return success({"profile_session_id": session["id"]}, "暂无对话记录")
        return success(
            {
                "profile_session_id": session["id"],
                "messages": _json_loads(row.get("messages"), []),
                "answer_map": _json_loads(row.get("answer_map"), {}),
                "extra_notes": _json_loads(row.get("extra_notes"), []),
                "current_index": int(row.get("current_index") or 0),
                "update_time": row.get("update_time"),
            },
            "对话记录读取成功",
        )
    except Exception as exc:
        return fail("对话记录读取失败", 500, {"error": str(exc)})


@profile_bp.post("/conversation")
@login_required
def save_conversation():
    try:
        payload = request.get_json(silent=True) or {}
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        _save_conversation_payload(request.user_id, session["id"], payload)
        return success({"profile_session_id": session["id"]}, "对话记录保存成功")
    except Exception as exc:
        return fail("对话记录保存失败", 500, {"error": str(exc)})


@profile_bp.delete("/conversation")
@login_required
def clear_conversation():
    try:
        session = _resolve_session(request.user_id, create_if_missing=False)
        if session:
            mysql_db.delete(
                "profile_conversation",
                "user_id=%s AND profile_session_id=%s",
                (request.user_id, session["id"]),
            )
        return success({}, "对话记录已清空")
    except Exception as exc:
        return fail("对话记录清空失败", 500, {"error": str(exc)})
