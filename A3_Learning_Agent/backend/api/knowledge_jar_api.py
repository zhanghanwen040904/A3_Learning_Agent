import json
from typing import Any, Dict, Iterable, List

from flask import Blueprint, request

from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session


knowledge_jar_bp = Blueprint("knowledge_jar", __name__)
JAR_EVENT_TYPES = ("knowledge_jar_add", "knowledge_jar_remove")


def _clean_point(value: Any) -> str:
    return " ".join(str(value or "").strip().split())[:160]


def _decode_detail(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _jar_state(user_id: int) -> Dict[str, Dict[str, Any]]:
    rows = mysql_db.query_all(
        """
        SELECT id, profile_session_id, event_type, knowledge_point, detail, create_time
        FROM learning_event
        WHERE user_id=%s AND event_type IN (%s, %s)
        ORDER BY create_time DESC, id DESC
        """,
        (user_id, *JAR_EVENT_TYPES),
    )
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        point = _clean_point(row.get("knowledge_point"))
        key = point.casefold()
        if not point or key in latest:
            continue
        detail = _decode_detail(row.get("detail"))
        latest[key] = {
            "id": row.get("id"),
            "knowledge_point": point,
            "active": row.get("event_type") == "knowledge_jar_add",
            "profile_session_id": row.get("profile_session_id"),
            "source": detail.get("source") or "manual",
            "source_label": detail.get("source_label") or "手动收藏",
            "stage_index": detail.get("stage_index"),
            "stage_title": detail.get("stage_title") or "",
            "mastery_score": detail.get("mastery_score"),
            "auto_collected": bool(detail.get("auto_collected")),
            "create_time": row.get("create_time"),
        }
    return latest


def record_knowledge_collections(
    user_id: int,
    profile_session_id: int,
    points: Iterable[Any],
    *,
    source: str = "manual",
    source_label: str = "手动收藏",
    stage_index: Any = None,
    stage_title: str = "",
    auto_collected: bool = False,
) -> List[str]:
    current = _jar_state(user_id)
    added: List[str] = []
    seen = set()
    for raw_point in points:
        point = _clean_point(raw_point)
        key = point.casefold()
        if not point or key in seen or current.get(key, {}).get("active"):
            continue
        seen.add(key)
        detail = {
            "source": str(source or "manual")[:40],
            "source_label": str(source_label or "手动收藏")[:80],
            "stage_index": stage_index,
            "stage_title": str(stage_title or "")[:120],
            "auto_collected": bool(auto_collected),
        }
        mysql_db.insert(
            "learning_event",
            {
                "user_id": user_id,
                "profile_session_id": profile_session_id,
                "event_type": "knowledge_jar_add",
                "knowledge_point": point,
                "detail": json.dumps(detail, ensure_ascii=False),
            },
        )
        added.append(point)
    return added


@knowledge_jar_bp.get("/")
@login_required
def list_knowledge_jar():
    try:
        items = [item for item in _jar_state(request.user_id).values() if item["active"]]
        items.sort(key=lambda item: (str(item.get("create_time") or ""), item.get("id") or 0), reverse=True)
        auto_count = sum(1 for item in items if item["auto_collected"])
        stages = {item["stage_title"] for item in items if item.get("stage_title")}
        return success(
            {
                "items": items,
                "stats": {
                    "total": len(items),
                    "auto_count": auto_count,
                    "manual_count": len(items) - auto_count,
                    "stage_count": len(stages),
                },
            },
            "知识收藏瓶查询成功",
        )
    except Exception as exc:
        return fail("知识收藏瓶查询失败", 500, {"error": str(exc)})


@knowledge_jar_bp.post("/collect")
@login_required
def collect_knowledge():
    try:
        payload = request.get_json(silent=True) or {}
        point = _clean_point(payload.get("knowledge_point"))
        if not point:
            return fail("知识点不能为空", 400)
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        if not session:
            return fail("未找到画像会话，无法收藏知识点", 404)
        added = record_knowledge_collections(
            request.user_id,
            session["id"],
            [point],
            source=payload.get("source") or "manual",
            source_label=payload.get("source_label") or "学习路径手动收藏",
            stage_index=payload.get("stage_index"),
            stage_title=payload.get("stage_title") or "",
            auto_collected=False,
        )
        return success({"knowledge_point": point, "collected": True, "created": bool(added)}, "已加入AI知识收藏瓶")
    except Exception as exc:
        return fail("知识点收藏失败", 500, {"error": str(exc)})


@knowledge_jar_bp.post("/remove")
@login_required
def remove_knowledge():
    try:
        payload = request.get_json(silent=True) or {}
        point = _clean_point(payload.get("knowledge_point"))
        if not point:
            return fail("知识点不能为空", 400)
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        if not session:
            return fail("未找到画像会话，无法移出知识点", 404)
        current = _jar_state(request.user_id).get(point.casefold(), {})
        if current.get("active"):
            mysql_db.insert(
                "learning_event",
                {
                    "user_id": request.user_id,
                    "profile_session_id": session["id"],
                    "event_type": "knowledge_jar_remove",
                    "knowledge_point": point,
                    "detail": json.dumps({"source": "manual_remove"}, ensure_ascii=False),
                },
            )
        return success({"knowledge_point": point, "collected": False}, "已从知识收藏瓶移出")
    except Exception as exc:
        return fail("移出知识点失败", 500, {"error": str(exc)})
