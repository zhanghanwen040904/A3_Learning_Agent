import json
import re
from typing import Optional

from flask import Blueprint, request

from ai.agents import ConversationAgent, ProfileAgent
from ai.llm_api import audit_content
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

profile_bp = Blueprint("profile", __name__)
profile_agent = ProfileAgent()
conversation_agent = ConversationAgent()

PROFILE_FIELDS = [
    "major",
    "target_course",
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "preferred_resource",
    "knowledge_level",
    "study_style",
    "weak_points",
    "challenge_scene",
    "profile_summary",
]

CORE_PROFILE_DIMENSIONS = [
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "preferred_resource",
]

DEFAULT_VALUE = "待进一步观察"
AGGREGATE_PROFILE_SESSION_ID = 0
DIMENSION_LABELS = {
    "knowledge_base": "知识基础",
    "cognitive_style": "认知风格",
    "error_prone_points": "易错点偏好",
    "study_goal": "学习目标",
    "learning_history": "学习历史",
    "course_progress": "课程进度",
    "study_time_prefer": "时间节奏",
    "preferred_resource": "资源偏好",
}


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


def _profile_session_id_from_payload(payload: Optional[dict] = None):
    payload = payload or {}
    raw = payload.get("profile_session_id") or request.args.get("profile_session_id")
    if raw in (None, "", "null", "undefined"):
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _sync_profile_aliases(profile: dict) -> dict:
    alias_pairs = [
        ("knowledge_base", "knowledge_level"),
        ("cognitive_style", "study_style"),
        ("error_prone_points", "weak_points"),
    ]
    for primary, legacy in alias_pairs:
        primary_value = profile.get(primary) or DEFAULT_VALUE
        legacy_value = profile.get(legacy) or DEFAULT_VALUE
        if primary_value == DEFAULT_VALUE and legacy_value != DEFAULT_VALUE:
            profile[primary] = legacy_value
        if legacy_value == DEFAULT_VALUE and profile.get(primary) != DEFAULT_VALUE:
            profile[legacy] = profile[primary]
    if (profile.get("challenge_scene") or DEFAULT_VALUE) == DEFAULT_VALUE and profile.get("error_prone_points") != DEFAULT_VALUE:
        profile["challenge_scene"] = profile["error_prone_points"]
    return profile


def _profile_only(data: Optional[dict] = None) -> dict:
    data = data or {}
    profile = {field: str(data.get(field) or DEFAULT_VALUE) for field in PROFILE_FIELDS}
    _sync_profile_aliases(profile)
    profile["profile_summary"] = profile_agent._build_summary(profile)
    return profile

def _empty_profile(session_id=None):
    data = {"profile_session_id": session_id}
    data.update({field: DEFAULT_VALUE for field in PROFILE_FIELDS})
    return data


def _user_personal_info(user_id: int) -> dict:
    row = mysql_db.query_one("SELECT major, target_course, education_level, school, personal_info FROM `user` WHERE id=%s", (user_id,)) or {}
    extra = _json_loads(row.get("personal_info"), {})
    if not isinstance(extra, dict):
        extra = {}
    return {
        "major": row.get("major") or extra.get("major") or "",
        "target_course": row.get("target_course") or extra.get("target_course") or "",
        "education_level": row.get("education_level") or extra.get("education_level") or "",
        "school": row.get("school") or extra.get("school") or "",
        **{k: v for k, v in extra.items() if k not in {"major", "target_course", "education_level", "school"}},
    }


def _merge_personal_info(profile: dict, personal: Optional[dict] = None) -> dict:
    personal = personal or {}
    merged = dict(profile or {})
    for key in ["major", "target_course"]:
        if personal.get(key) and (not merged.get(key) or merged.get(key) == DEFAULT_VALUE):
            merged[key] = personal[key]
    return merged


def _session_belongs_to_user(user_id: int, session_id: int) -> bool:
    return bool(mysql_db.query_one("SELECT id FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id)))


def _set_active_session(user_id: int, session_id: int) -> None:
    mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    mysql_db.update("profile_session", {"is_active": 1}, "id=%s AND user_id=%s", (session_id, user_id))


def _create_session(user_id: int, title: Optional[str] = None, activate: bool = True) -> dict:
    existing_count = mysql_db.query_one("SELECT COUNT(*) AS total FROM profile_session WHERE user_id=%s", (user_id,)) or {}
    default_title = title or f"画像对话 {int(existing_count.get('total') or 0) + 1}"
    if activate:
        mysql_db.update("profile_session", {"is_active": 0}, "user_id=%s", (user_id,))
    session_id = mysql_db.insert("profile_session", {"user_id": user_id, "title": default_title, "is_active": 1 if activate else 0})
    return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s", (session_id,))


def _active_session(user_id: int, create_if_missing: bool = False):
    row = mysql_db.query_one("SELECT * FROM profile_session WHERE user_id=%s AND is_active=1 ORDER BY update_time DESC LIMIT 1", (user_id,))
    if row:
        return row
    row = mysql_db.query_one("SELECT * FROM profile_session WHERE user_id=%s ORDER BY update_time DESC LIMIT 1", (user_id,))
    if row:
        _set_active_session(user_id, row["id"])
        row["is_active"] = 1
        return row
    if create_if_missing:
        return _create_session(user_id, activate=True)
    return None


def _resolve_session(user_id: int, payload: Optional[dict] = None, create_if_missing: bool = False):
    session_id = _profile_session_id_from_payload(payload)
    if session_id is not None:
        if not _session_belongs_to_user(user_id, session_id):
            return None
        return mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id))
    return _active_session(user_id, create_if_missing=create_if_missing)


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
    mysql_db.upsert_by_unique_key("profile_conversation", data, update_fields=["messages", "answer_map", "extra_notes", "current_index"])


def _persist_profile_result(user_id: int, session_id: int, session: dict, profile_result: dict) -> dict:
    profile_data = {
        "user_id": user_id,
        "profile_session_id": session_id,
        **{field: profile_result.get("profile", {}).get(field, DEFAULT_VALUE) for field in PROFILE_FIELDS},
    }
    mysql_db.upsert_by_unique_key("student_profile", profile_data, update_fields=["profile_session_id", *PROFILE_FIELDS])

    session_title = (
        profile_data.get("profile_summary")
        or profile_data.get("target_course")
        or profile_data.get("major")
        or session.get("title")
    )
    if session_title:
        mysql_db.update("profile_session", {"title": str(session_title)[:120]}, "id=%s AND user_id=%s", (session_id, user_id))

    aggregate_profile = _aggregate_profile_payload(
        user_id,
        _refresh_aggregate_profile(user_id, transient_profile=profile_result.get("profile")),
    )
    return {
        **profile_result,
        "profile_session_id": session_id,
        "aggregate_profile": aggregate_profile,
    }


def _delete_session_outputs(user_id: int, session_id: int) -> None:
    resources = mysql_db.query_all("SELECT id FROM study_resource WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
    for item in resources:
        mysql_db.delete("resource_source", "resource_id=%s", (item["id"],))
        mysql_db.delete("resource_feedback", "user_id=%s AND resource_id=%s", (user_id, item["id"]))
    batches = mysql_db.query_all("SELECT id FROM generation_batch WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
    for item in batches:
        mysql_db.delete("agent_execution", "batch_id=%s", (item["id"],))
    mysql_db.delete("study_resource", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("study_path", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("generation_batch", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("tutor_conversation", "user_id=%s AND profile_session_id=%s", (user_id, session_id))


def _delete_profile_session(user_id: int, session_id: int) -> None:
    mysql_db.delete("student_profile", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("profile_conversation", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    mysql_db.delete("learning_event", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
    _delete_session_outputs(user_id, session_id)
    mysql_db.delete("profile_session", "id=%s AND user_id=%s", (session_id, user_id))


def _all_conversation_messages(user_id: int) -> list:
    rows = mysql_db.query_all(
        """
        SELECT profile_session_id, messages, update_time
        FROM profile_conversation
        WHERE user_id=%s
        ORDER BY update_time ASC, profile_session_id ASC
        """,
        (user_id,),
    )
    result = []
    for row in rows:
        messages = _json_loads(row.get("messages"), [])
        if isinstance(messages, list) and messages:
            result.append({"profile_session_id": row.get("profile_session_id"), "messages": messages})
    return result


def _aggregate_profile_data(user_id: int, transient_profile: Optional[dict] = None) -> dict:
    merged = _profile_only({})

    for item in _all_conversation_messages(user_id):
        dialogue = profile_agent._messages_to_dialogue(item.get("messages") or [])
        if dialogue.strip():
            parsed = profile_agent._extract_from_dialogue(dialogue)
            merged = profile_agent._merge_profile(merged, _profile_only(parsed))

    rows = mysql_db.query_all(
        """
        SELECT *
        FROM student_profile
        WHERE user_id=%s AND profile_session_id <> %s
        ORDER BY update_time ASC, profile_session_id ASC
        """,
        (user_id, AGGREGATE_PROFILE_SESSION_ID),
    )
    for row in rows:
        merged = profile_agent._merge_profile(merged, _profile_only(row))

    if transient_profile:
        merged = profile_agent._merge_profile(merged, _profile_only(transient_profile))

    merged = _merge_personal_info(merged, _user_personal_info(user_id))
    merged = _profile_only(merged)
    return {"user_id": user_id, "profile_session_id": AGGREGATE_PROFILE_SESSION_ID, **merged}


def _refresh_aggregate_profile(user_id: int, transient_profile: Optional[dict] = None) -> dict:
    data = _aggregate_profile_data(user_id, transient_profile=transient_profile)
    mysql_db.upsert_by_unique_key("student_profile", data, update_fields=["profile_session_id", *PROFILE_FIELDS])
    return data


def _cached_aggregate_profile(user_id: int) -> Optional[dict]:
    row = mysql_db.query_one(
        "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
        (user_id, AGGREGATE_PROFILE_SESSION_ID),
    )
    if not row:
        return None
    return {"user_id": user_id, "profile_session_id": AGGREGATE_PROFILE_SESSION_ID, **_profile_only(row)}


def _normalize_text(value) -> str:
    text = str(value or "").strip()
    return "" if text in ("", DEFAULT_VALUE, "None", "null", "undefined") else text


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _score_level(score: int) -> str:
    if score >= 85:
        return "高"
    if score >= 65:
        return "中"
    return "低"


def _clamp_score(score: int) -> int:
    return max(0, min(100, int(score)))


def _portrait_dimension_scores(user_id: int, profile: dict) -> dict:
    quiz_rows = mysql_db.query_all(
        "SELECT score, knowledge_point, create_time FROM quiz_result WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )
    mastery_rows = mysql_db.query_all(
        "SELECT knowledge_point, mastery_score, weak_reason FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC, update_time DESC LIMIT 50",
        (user_id,),
    )
    event_rows = mysql_db.query_all(
        "SELECT event_type, knowledge_point, detail, create_time FROM learning_event WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )
    resource_feedback_rows = mysql_db.query_all(
        "SELECT rating, comment FROM resource_feedback WHERE user_id=%s ORDER BY create_time DESC LIMIT 30",
        (user_id,),
    )
    session_rows = mysql_db.query_all(
        "SELECT id, title, create_time FROM profile_session WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )
    resource_rows = mysql_db.query_all(
        "SELECT resource_type, title FROM study_resource WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )

    quiz_scores = [int(item.get("score") or 0) for item in quiz_rows]
    avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else 0
    weak_mastery = [item for item in mastery_rows if int(item.get("mastery_score") or 0) < 70]
    strong_mastery = [item for item in mastery_rows if int(item.get("mastery_score") or 0) >= 85]
    avg_mastery = round(sum(int(item.get("mastery_score") or 0) for item in mastery_rows) / len(mastery_rows), 1) if mastery_rows else 0
    session_count = len(session_rows)
    quiz_count = len(quiz_rows)
    resource_count = len(resource_rows)
    feedback_count = len(resource_feedback_rows)

    profile_text = {key: _normalize_text(profile.get(key)) for key in DIMENSION_LABELS}
    profile_text["major"] = _normalize_text(profile.get("major"))
    profile_text["target_course"] = _normalize_text(profile.get("target_course"))

    goal_text = profile_text["study_goal"]
    history_text = profile_text["learning_history"]
    progress_text = profile_text["course_progress"]
    knowledge_text = profile_text["knowledge_base"]
    style_text = profile_text["cognitive_style"]
    weak_text = profile_text["error_prone_points"]
    time_text = profile_text["study_time_prefer"]
    resource_text = profile_text["preferred_resource"]

    quantified_goal = bool(re.search(r"\d+|期末|考研|通过|拿到|达到|冲刺|目标", goal_text))
    progress_markers = bool(re.search(r"第.{0,4}[章节单元]|已学|正在学|完成|复习|进度|阶段", progress_text + history_text))
    time_markers = _contains_any(time_text, ["早上", "上午", "中午", "下午", "晚上", "夜间", "周末", "碎片", "固定", "睡前"])
    style_markers = _contains_any(style_text + resource_text, ["图解", "视频", "代码", "案例", "刷题", "自学", "讲解", "练习", "思维导图"])
    history_markers = _contains_any(history_text, ["学过", "做过", "之前", "上学期", "这学期", "复习", "接触过", "基础"])
    weak_markers = _contains_any(weak_text, ["不会", "模糊", "薄弱", "容易错", "混淆", "卡住", "困难"])
    resource_markers = _contains_any(resource_text, ["视频", "文档", "题目", "代码", "案例", "动画", "讲义", "思维导图"])

    scores = {}

    knowledge_score = 15
    reasons = []
    if knowledge_text:
        knowledge_score += 25
        reasons.append("已从对话中识别出知识基础描述")
    if mastery_rows:
        knowledge_score += min(40, round(avg_mastery * 0.4))
        reasons.append(f"结合 {len(mastery_rows)} 条知识点掌握记录，平均掌握度 {avg_mastery}")
    elif quiz_rows:
        knowledge_score += min(25, round(avg_quiz_score * 0.25))
        reasons.append(f"结合 {quiz_count} 次练习结果，平均得分 {avg_quiz_score}")
    if weak_mastery:
        knowledge_score -= min(15, len(weak_mastery) * 3)
        reasons.append(f"检测到 {len(weak_mastery)} 个薄弱知识点")
    scores["knowledge_base"] = {
        "score": _clamp_score(knowledge_score),
        "level": _score_level(_clamp_score(knowledge_score)),
        "reason": "；".join(reasons) or "当前主要依据对话信息判断，缺少练习数据支撑。",
    }

    style_score = 20
    reasons = []
    if style_text:
        style_score += 35
        reasons.append("已识别明确的认知风格描述")
    if resource_text:
        style_score += 15
        reasons.append("资源偏好可辅助推断学习风格")
    if style_markers:
        style_score += 15
        reasons.append("对话中出现了图解、视频、刷题、代码等偏好线索")
    if session_count >= 3:
        style_score += min(15, session_count * 2)
        reasons.append(f"已累计 {session_count} 个会话，风格判断更稳定")
    scores["cognitive_style"] = {
        "score": _clamp_score(style_score),
        "level": _score_level(_clamp_score(style_score)),
        "reason": "；".join(reasons) or "当前只识别到少量风格线索，仍需更多自然对话。",
    }

    weak_score = 15
    reasons = []
    if weak_text:
        weak_score += 30
        reasons.append("已识别出学生主动提到的薄弱点")
    if weak_markers:
        weak_score += 10
    if weak_mastery:
        weak_score += min(30, len(weak_mastery) * 8)
        reasons.append(f"练习结果中有 {len(weak_mastery)} 个掌握度偏低的知识点")
    if quiz_rows and avg_quiz_score < 75:
        weak_score += 15
        reasons.append(f"平均练习得分 {avg_quiz_score}，说明仍存在明显薄弱环节")
    scores["error_prone_points"] = {
        "score": _clamp_score(weak_score),
        "level": _score_level(_clamp_score(weak_score)),
        "reason": "；".join(reasons) or "当前主要依据少量对话判断，尚未形成稳定错因画像。",
    }

    goal_score = 20
    reasons = []
    if goal_text:
        goal_score += 35
        reasons.append("已识别明确学习目标")
    if quantified_goal:
        goal_score += 20
        reasons.append("目标中含有量化表述或阶段性目标")
    if profile_text["target_course"]:
        goal_score += 10
        reasons.append("已识别目标课程")
    if profile_text["major"]:
        goal_score += 10
        reasons.append("已识别专业背景，可帮助目标聚焦")
    scores["study_goal"] = {
        "score": _clamp_score(goal_score),
        "level": _score_level(_clamp_score(goal_score)),
        "reason": "；".join(reasons) or "当前尚未识别出清晰、可执行的学习目标。",
    }

    history_score = 15
    reasons = []
    if history_text:
        history_score += 35
        reasons.append("已识别学习经历描述")
    if history_markers:
        history_score += 10
        reasons.append("对话中包含过往课程/基础/复习经历")
    if session_count:
        history_score += min(20, session_count * 3)
        reasons.append(f"累计 {session_count} 个对话会话")
    if quiz_count:
        history_score += min(20, quiz_count * 3)
        reasons.append(f"已有 {quiz_count} 次练习记录")
    scores["learning_history"] = {
        "score": _clamp_score(history_score),
        "level": _score_level(_clamp_score(history_score)),
        "reason": "；".join(reasons) or "目前学习历史信息还比较少。",
    }

    progress_score = 15
    reasons = []
    if progress_text:
        progress_score += 30
        reasons.append("已识别课程进度描述")
    if progress_markers:
        progress_score += 15
        reasons.append("出现章节、阶段、完成情况等进度线索")
    if quiz_count:
        progress_score += min(20, quiz_count * 2)
        reasons.append("已有练习数据可辅助判断进度")
    if resource_count:
        progress_score += min(20, resource_count * 2)
        reasons.append(f"已生成/使用 {resource_count} 份学习资源")
    if strong_mastery:
        progress_score += min(10, len(strong_mastery) * 3)
        reasons.append(f"已有 {len(strong_mastery)} 个较强知识点")
    scores["course_progress"] = {
        "score": _clamp_score(progress_score),
        "level": _score_level(_clamp_score(progress_score)),
        "reason": "；".join(reasons) or "当前课程进度主要依赖对话描述，行为证据仍较少。",
    }

    time_score = 15
    reasons = []
    if time_text:
        time_score += 45
        reasons.append("已识别固定学习时段/节奏描述")
    if time_markers:
        time_score += 15
        reasons.append("出现早晚、周末、碎片化等时间节奏关键词")
    if session_count >= 2:
        time_score += min(15, session_count * 2)
        reasons.append("多轮会话有助于稳定识别节奏偏好")
    scores["study_time_prefer"] = {
        "score": _clamp_score(time_score),
        "level": _score_level(_clamp_score(time_score)),
        "reason": "；".join(reasons) or "尚未积累出明确的学习时间规律。",
    }

    resource_score = 15
    reasons = []
    if resource_text:
        resource_score += 35
        reasons.append("已识别资源形式偏好")
    if resource_markers:
        resource_score += 15
        reasons.append("出现视频、文档、代码、题目等资源关键词")
    if resource_count:
        resource_score += min(20, resource_count * 2)
        reasons.append(f"已有 {resource_count} 份资源使用/生成记录")
    if feedback_count:
        avg_rating = round(sum(int(item.get("rating") or 0) for item in resource_feedback_rows) / feedback_count, 1)
        resource_score += min(15, feedback_count * 3)
        reasons.append(f"已有 {feedback_count} 条资源反馈，平均评分 {avg_rating}")
    scores["preferred_resource"] = {
        "score": _clamp_score(resource_score),
        "level": _score_level(_clamp_score(resource_score)),
        "reason": "；".join(reasons) or "当前对资源偏好的判断还较初步。",
    }

    return {
        "dimensions": scores,
        "overall_score": round(sum(item["score"] for item in scores.values()) / max(len(scores), 1), 1),
        "evidence": {
            "session_count": session_count,
            "quiz_count": quiz_count,
            "avg_quiz_score": avg_quiz_score,
            "mastery_count": len(mastery_rows),
            "resource_count": resource_count,
            "feedback_count": feedback_count,
            "event_count": len(event_rows),
        },
        "method": "综合对话画像、练习成绩、知识点掌握记录、资源使用和学习行为事件进行评分。",
    }


def _aggregate_profile_payload(user_id: int, profile: dict) -> dict:
    payload = dict(profile or {})
    payload["portrait_scoring"] = _portrait_dimension_scores(user_id, payload)
    return payload


@profile_bp.get("/user-info")
@login_required
def get_user_info():
    try:
        return success(_user_personal_info(request.user_id), "个人信息读取成功")
    except Exception as exc:
        return fail("个人信息读取失败", 500, {"error": str(exc)})


@profile_bp.post("/user-info")
@login_required
def save_user_info():
    try:
        payload = request.get_json(silent=True) or {}
        data = {
            "major": str(payload.get("major") or "").strip()[:120] or None,
            "target_course": str(payload.get("target_course") or "").strip()[:120] or None,
            "education_level": str(payload.get("education_level") or "").strip()[:80] or None,
            "school": str(payload.get("school") or "").strip()[:160] or None,
        }
        extra = payload.get("personal_info") if isinstance(payload.get("personal_info"), dict) else {}
        data["personal_info"] = _json_dumps({**extra, **{k: v for k, v in data.items() if k != "personal_info" and v}})
        mysql_db.update("user", data, "id=%s", (request.user_id,))
        _refresh_aggregate_profile(request.user_id, transient_profile=_merge_personal_info({}, data))
        return success(_user_personal_info(request.user_id), "个人信息已保存")
    except Exception as exc:
        return fail("个人信息保存失败", 500, {"error": str(exc)})


@profile_bp.get("/sessions")
@login_required
def list_sessions():
    try:
        session = _active_session(request.user_id, create_if_missing=False)
        rows = mysql_db.query_all(
            """
            SELECT ps.*, sp.profile_summary, sp.major, sp.target_course, sp.update_time AS profile_update_time,
                   pc.messages AS conversation_messages
            FROM profile_session ps
            LEFT JOIN student_profile sp ON sp.user_id = ps.user_id AND sp.profile_session_id = ps.id
            LEFT JOIN profile_conversation pc ON pc.user_id = ps.user_id AND pc.profile_session_id = ps.id
            WHERE ps.user_id=%s
            ORDER BY ps.is_active DESC, ps.update_time DESC, ps.id DESC
            """,
            (request.user_id,),
        )
        for row in rows:
            messages = _json_loads(row.get("conversation_messages"), [])
            row["message_count"] = len(messages) if isinstance(messages, list) else 0
            row.pop("conversation_messages", None)
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
        _refresh_aggregate_profile(request.user_id)
        return success({"profile_session_id": session_id, "profile": _empty_profile(session_id)}, "画像会话已清空")
    except Exception as exc:
        return fail("画像会话清空失败", 500, {"error": str(exc)})


@profile_bp.patch("/sessions/<int:session_id>")
@login_required
def rename_session(session_id: int):
    try:
        if not _session_belongs_to_user(request.user_id, session_id):
            return fail("画像会话不存在", 404)
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title") or "").strip()
        if not title:
            return fail("会话名称不能为空", 400)
        if len(title) > 120:
            title = title[:120]
        mysql_db.update("profile_session", {"title": title}, "id=%s AND user_id=%s", (session_id, request.user_id))
        session = mysql_db.query_one("SELECT * FROM profile_session WHERE id=%s AND user_id=%s", (session_id, request.user_id))
        return success(session, "画像会话已重命名")
    except Exception as exc:
        return fail("画像会话重命名失败", 500, {"error": str(exc)})


@profile_bp.delete("/sessions/<int:session_id>")
@login_required
def delete_session(session_id: int):
    try:
        if not _session_belongs_to_user(request.user_id, session_id):
            return fail("画像会话不存在", 404)
        current = mysql_db.query_one("SELECT is_active FROM profile_session WHERE id=%s AND user_id=%s", (session_id, request.user_id)) or {}
        _delete_profile_session(request.user_id, session_id)
        _refresh_aggregate_profile(request.user_id)
        next_session = _active_session(request.user_id, create_if_missing=False)
        if current.get("is_active") and next_session:
            _set_active_session(request.user_id, next_session["id"])
        if not next_session:
            next_session = _create_session(request.user_id, activate=True)
        return success({"active_session_id": next_session["id"] if next_session else None}, "画像会话已删除")
    except Exception as exc:
        return fail("画像会话删除失败", 500, {"error": str(exc)})


@profile_bp.post("/chat")
@login_required
def chat_profile():
    try:
        payload = request.get_json(silent=True) or {}
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        _set_active_session(request.user_id, session["id"])

        messages = payload.get("messages") or []
        personal_info = _user_personal_info(request.user_id)
        current_profile = _merge_personal_info(payload.get("current_profile") or {}, personal_info)
        if not isinstance(messages, list) or not messages:
            return fail("缺少有效的多轮对话 messages", 400)

        latest_user_text = "\n".join(str(item.get("content") or "") for item in messages if item.get("role") == "user")
        if not latest_user_text.strip():
            return fail("请先输入学生自然语言回答", 400)
        if not audit_content(latest_user_text):
            return fail("学生对话未通过内容审核", 403)

        conversation_result = conversation_agent.respond(messages, current_profile)
        _save_conversation_payload(request.user_id, session["id"], {"messages": messages})
        result = {
            **conversation_result,
            "profile_session_id": session["id"],
            "reply_type": "rich_answer",
            "next_question": "",
            "profile_sync_pending": True,
        }
        return success(result, "对话回答成功")
    except Exception as exc:
        return fail("画像对话分析失败", 500, {"error": str(exc)})


@profile_bp.post("/chat/profile-sync")
@login_required
def chat_profile_sync():
    try:
        payload = request.get_json(silent=True) or {}
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        _set_active_session(request.user_id, session["id"])

        messages = payload.get("messages") or []
        current_profile = payload.get("current_profile") or {}
        if not isinstance(messages, list) or not messages:
            return fail("缺少有效的多轮对话 messages", 400)

        latest_user_text = "\n".join(str(item.get("content") or "") for item in messages if item.get("role") == "user")
        if not latest_user_text.strip():
            return fail("请先输入学生自然语言回答", 400)
        if not audit_content(latest_user_text):
            return fail("学生对话未通过内容审核", 403)

        profile_result = profile_agent.chat_extract(messages, current_profile)
        _save_conversation_payload(request.user_id, session["id"], {"messages": messages})
        result = _persist_profile_result(request.user_id, session["id"], session, profile_result)
        return success(result, "画像已完成静默更新")
    except Exception as exc:
        return fail("画像静默更新失败", 500, {"error": str(exc)})


@profile_bp.post("/chat/enhance")
@login_required
def chat_enhance():
    try:
        payload = request.get_json(silent=True) or {}
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)

        messages = payload.get("messages") or []
        current_profile = payload.get("current_profile") or {}
        assistant_reply = str(payload.get("assistant_reply") or "").strip()
        need_diagram = bool(payload.get("need_diagram"))
        need_quiz = bool(payload.get("need_quiz"))

        if not isinstance(messages, list) or not messages:
            return fail("缺少有效的多轮对话 messages", 400)
        if not assistant_reply:
            return fail("缺少主回答内容 assistant_reply", 400)
        if not need_diagram and not need_quiz:
            return success({
                "diagram_image": "",
                "quiz_items": [],
                "need_diagram": False,
                "need_quiz": False,
                "profile_session_id": session["id"],
            }, "当前无需增强内容")

        result = conversation_agent.enhance(
            messages=messages,
            answer=assistant_reply,
            profile=current_profile,
            need_diagram=need_diagram,
            need_quiz=need_quiz,
        )
        return success({
            **result,
            "profile_session_id": session["id"],
        }, "增强内容生成成功")
    except Exception as exc:
        return fail("增强内容生成失败", 500, {"error": str(exc)})


@profile_bp.post("/create")
@login_required
def create_profile():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["dialogue"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        dialogue = str(payload["dialogue"])
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        session_id = session["id"]
        _set_active_session(request.user_id, session_id)

        if not audit_content(dialogue):
            return fail("学生对话未通过内容审核", 403)

        profile_payload = payload.get("profile") if isinstance(payload.get("profile"), dict) else None
        personal_info = _user_personal_info(request.user_id)
        analyzed_profile = _merge_personal_info(profile_agent.analyze(dialogue), personal_info)
        profile = profile_agent._merge_profile(_merge_personal_info(profile_payload or {}, personal_info), analyzed_profile)
        data = {"user_id": request.user_id, "profile_session_id": session_id, **{field: profile.get(field, DEFAULT_VALUE) for field in PROFILE_FIELDS}}
        mysql_db.upsert_by_unique_key("student_profile", data, update_fields=["profile_session_id", *PROFILE_FIELDS])

        title = data.get("profile_summary") or data.get("target_course") or data.get("major") or session.get("title")
        mysql_db.update("profile_session", {"title": str(title)[:120]}, "id=%s AND user_id=%s", (session_id, request.user_id))

        conversation = payload.get("conversation")
        if isinstance(conversation, dict):
            _save_conversation_payload(request.user_id, session_id, conversation)

        _delete_session_outputs(request.user_id, session_id)
        aggregate_profile = _aggregate_profile_payload(
            request.user_id,
            _refresh_aggregate_profile(request.user_id, transient_profile=profile),
        )
        return success({**data, "aggregate_profile": aggregate_profile}, "画像创建成功")
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

        learning_data = str(payload["learning_data"])
        session = _resolve_session(request.user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        session_id = session["id"]

        if not audit_content(learning_data):
            return fail("学习数据未通过内容审核", 403)

        old_profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (request.user_id, session_id)) or {}
        dialogue = f"历史画像：{old_profile}\n最新学习数据：{learning_data}"
        profile = profile_agent.analyze(dialogue)
        data = {field: profile.get(field, DEFAULT_VALUE) for field in PROFILE_FIELDS}
        affected = mysql_db.update("student_profile", data, "user_id=%s AND profile_session_id=%s", (request.user_id, session_id))
        if affected == 0:
            mysql_db.insert("student_profile", {"user_id": request.user_id, "profile_session_id": session_id, **data})

        _delete_session_outputs(request.user_id, session_id)
        aggregate_profile = _aggregate_profile_payload(
            request.user_id,
            _refresh_aggregate_profile(request.user_id, transient_profile=data),
        )
        return success({"user_id": request.user_id, "profile_session_id": session_id, **data, "aggregate_profile": aggregate_profile}, "画像更新成功")
    except Exception as exc:
        return fail("画像更新失败", 500, {"error": str(exc)})


@profile_bp.get("/")
@login_required
def get_my_profile():
    try:
        session = _resolve_session(request.user_id, create_if_missing=False)
        if not session:
            return success(_empty_profile(), "暂无画像")
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (request.user_id, session["id"]))
        personal_info = _user_personal_info(request.user_id)
        return success(_merge_personal_info(profile or _empty_profile(session["id"]), personal_info), "查询成功")
    except Exception as exc:
        return fail("画像查询失败", 500, {"error": str(exc)})


@profile_bp.get("/aggregate")
@login_required
def get_aggregate_profile():
    try:
        profile = _cached_aggregate_profile(request.user_id)
        if not profile:
            profile = _refresh_aggregate_profile(request.user_id)
        profile = _merge_personal_info(profile, _user_personal_info(request.user_id))
        return success(_aggregate_profile_payload(request.user_id, profile), "综合画像读取成功")
    except Exception as exc:
        return fail("综合画像读取失败", 500, {"error": str(exc)})


@profile_bp.get("/<int:user_id>")
@login_required
def get_profile(user_id: int):
    return get_my_profile()


@profile_bp.get("/conversation")
@login_required
def get_conversation():
    try:
        session = _resolve_session(request.user_id, create_if_missing=False)
        if not session:
            return success({}, "暂无对话记录")
        row = mysql_db.query_one("SELECT * FROM profile_conversation WHERE user_id=%s AND profile_session_id=%s", (request.user_id, session["id"]))
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
            mysql_db.delete("profile_conversation", "user_id=%s AND profile_session_id=%s", (request.user_id, session["id"]))
            _refresh_aggregate_profile(request.user_id)
        return success({}, "对话记录已清空")
    except Exception as exc:
        return fail("对话记录清空失败", 500, {"error": str(exc)})
