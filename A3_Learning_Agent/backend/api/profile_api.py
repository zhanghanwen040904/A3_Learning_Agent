import json
import re
from typing import Any, Optional

import pymysql
from flask import Blueprint, request

from ai.agents import ConversationAgent, ProfileAgent
from ai.llm_api import audit_content
from ai.langchain_parsers import parse_json_with_fallback
from ai.llm_adapter import PlatformLLM
from config import config
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

profile_bp = Blueprint("profile", __name__)
profile_agent = ProfileAgent()
conversation_agent = ConversationAgent()

PROFILE_FIELDS = [
    "major",
    "target_course",
    "current_topic",
    "mastery_level",
    "current_difficulty",
    "task_goal",
    "support_preference",
    "engagement_level",
    "learning_background",
    "recent_progress",
    "schedule_pattern",
    "preferred_resource",
    "weak_knowledge_points",
    "recommended_next_step",
    "portrait_confidence",
    "profile_summary",
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "knowledge_level",
    "study_style",
    "weak_points",
    "challenge_scene",
]

CORE_PROFILE_DIMENSIONS = [
    "current_topic",
    "mastery_level",
    "current_difficulty",
    "task_goal",
    "support_preference",
    "engagement_level",
]

DEFAULT_VALUE = "待进一步观察"
AGGREGATE_PROFILE_SESSION_ID = 0
DIMENSION_LABELS = {
    "current_topic": "当前学习主题",
    "mastery_level": "掌握程度",
    "current_difficulty": "当前困难点",
    "task_goal": "当前任务目标",
    "support_preference": "适配支持方式",
    "engagement_level": "学习投入状态",
}


def _is_missing_schema_error(exc: Exception) -> bool:
    if not isinstance(exc, pymysql.err.MySQLError):
        return False
    code = exc.args[0] if exc.args else None
    return code in (1054, 1146)

PORTRAIT_SCORE_PROMPT_TEMPLATE = """
你是一名“严谨、细腻、懂教学”的高校课程导师。现在请你不要把自己当成填表系统，而是当成一位真正看过学生对话、练习记录和学习行为之后，给学生写阶段性评语的老师。

你的任务不是机械判“字段有没有”，而是根据证据对学生当前学习状态做有温度但严格的判断，再把这种判断落到分数上。

请先在心里完成两步：
第一步：先形成整体判断——这个学生目前学到哪里、卡在哪里、目标是否明确、需要什么支持。
第二步：再基于整体判断，为每个维度打分并写出老师式评语。

非常重要的要求：
1. 严禁按“有内容就高分、没内容就低分”这种机械方式评分。
2. 严禁出现过于工整、呆板、模板化的分数分布，例如 60/70/80/90 一排，或者多个维度完全同分。
3. 分数要体现细微差别，优先使用更自然的具体分数，例如 67、72、78、83，而不是大量整十、整五。
4. 每个维度都要写得像老师评语：先说观察到的状态，再说为什么这样判断；可以指出证据不足，但不要只说“证据不足”。
5. 如果证据之间存在冲突，要明确写出“学生口头表达”和“行为/练习表现”之间的不一致。
6. 你评的是“学生当前状态”，不是“系统抽取字段的完整度”。
7. 只能输出 JSON，不要输出 markdown，不要输出解释性前后缀。

六个核心维度的评分含义如下：
- current_topic：学生当前聚焦内容是否明确，学习主线是否稳定。分高表示主线清晰，不飘散。
- mastery_level：学生对当前学习内容的真实掌握程度。分高表示理解较扎实、能迁移或能说清。
- current_difficulty：学生当前卡点的严重程度与可化解程度。分高表示困难较聚焦、可拆解、可解决；分低表示困难明显且阻碍较大。
- task_goal：学生眼下的学习目标是否明确、具体、可执行。分高表示目标清楚且有行动方向。
- support_preference：适合学生的帮助方式是否已经比较明确。分高表示已经能判断出更适合讲解、例题、图示、拆步骤等哪种支持。
- engagement_level：学生投入度、持续性和主动性。分高表示学习意愿较稳定、互动积极、能持续推进。

请输出严格符合以下 JSON 结构：
{{
  "teacher_summary": "",
  "overall_comment": "",
  "dimensions": {{
    "current_topic": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "mastery_level": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "current_difficulty": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "task_goal": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "support_preference": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "engagement_level": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }}
  }},
  "overall_score": 0,
  "completion_ratio": 0.0,
  "confidence_label": "低",
  "method": "基于多轮对话、练习记录和学习行为证据的大模型教师式综合评估",
  "evidence_summary": ""
}}

等级参考：
- 85-100：状态清晰且相对成熟
- 70-84：已有较稳定基础，但仍有明显提升空间
- 55-69：处于建立阶段，理解或目标仍不够稳
- 0-54：当前存在较大阻碍，亟需外部支持

每个维度的 teacher_judgement 请控制在 20~40 字，像老师写在学习记录上的一句核心判断。
每个维度的 reason 请控制在 40~90 字，说明你为什么给这个分。
teacher_summary 请用 80~140 字写一段整体教师评语。
overall_comment 请用一句话总结“下一步最该抓什么”。

学生画像：
{profile_json}

证据上下文：
{evidence_json}
""".strip()


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
    try:
        row = mysql_db.query_one("SELECT major, target_course, education_level, school, personal_info FROM `user` WHERE id=%s", (user_id,)) or {}
    except pymysql.err.MySQLError as exc:
        if not _is_missing_schema_error(exc):
            raise
        row = mysql_db.query_one("SELECT id FROM `user` WHERE id=%s", (user_id,)) or {}
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

    session_title = _session_knowledge_title(profile_data, session.get("title"))
    if session_title:
        mysql_db.update("profile_session", {"title": str(session_title)[:120]}, "id=%s AND user_id=%s", (session_id, user_id))

    aggregate_profile = _aggregate_profile_payload(
        user_id,
        _refresh_aggregate_profile(user_id, transient_profile=profile_result.get("profile")),
        refresh_scoring=True,
    )
    _persist_portrait_snapshot(
        user_id=user_id,
        profile_session_id=session_id,
        profile=aggregate_profile,
        portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
        trigger_source="chat_profile_sync",
        force=True,
    )
    aggregate_profile["portrait_history"] = _portrait_history(user_id, limit=6)
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
    mysql_db.delete("portrait_snapshot", "user_id=%s AND profile_session_id=%s", (user_id, session_id))
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


def _has_meaningful_profile(profile: Optional[dict]) -> bool:
    if not profile:
        return False
    meaningful_fields = [
        "current_topic",
        "mastery_level",
        "current_difficulty",
        "task_goal",
        "support_preference",
        "engagement_level",
        "weak_knowledge_points",
        "profile_summary",
    ]
    return any(_normalize_text((profile or {}).get(field)) for field in meaningful_fields)


def _ensure_session_profile_from_conversation(user_id: int, session: Optional[dict] = None) -> Optional[dict]:
    session = session or _active_session(user_id, create_if_missing=False)
    if not session:
        return None
    session_id = session["id"]
    existing = mysql_db.query_one(
        "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
        (user_id, session_id),
    )
    if _has_meaningful_profile(existing):
        return existing

    conversation = mysql_db.query_one(
        "SELECT messages FROM profile_conversation WHERE user_id=%s AND profile_session_id=%s",
        (user_id, session_id),
    ) or {}
    messages = _json_loads(conversation.get("messages"), [])
    if not isinstance(messages, list) or not any(item.get("role") == "user" and _normalize_text(item.get("content")) for item in messages):
        return existing

    current_profile = _profile_only(existing or {})
    profile_result = profile_agent.chat_extract(messages, current_profile)
    persisted = _persist_profile_result(user_id, session_id, session, profile_result)
    return persisted.get("profile") or profile_result.get("profile")


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


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return fallback


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _trim_text(value: Any, limit: int = 120) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    return text[:limit]


def _extract_knowledge_title(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""

    text = re.sub(r"^.*?方向[：:；;]\s*", "", text)
    text = re.sub(
        r"^(当前聚焦|聚焦|当前学习主题|学习主题|薄弱知识点|薄弱点|易错点|当前难点|知识点|章节)\s*[：:]?\s*",
        "",
        text,
    )
    if "聚焦" in text:
        after_focus = text.split("聚焦", 1)[1].strip(" ：:；;，,。 ")
        if after_focus:
            text = after_focus

    parts = re.split(r"[；;，,、/\n|]", text)
    parts = [part.strip(" ：:；;，,。!！?？·[]【】()（）\"'") for part in parts if part and part.strip()]
    if not parts:
        return ""

    for part in parts:
        if 1 <= len(part) <= 18:
            return part
    return parts[0][:24]


def _extract_segment_by_labels(value: Any, labels: list[str]) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[：:]\s*([^；;，,\n]+)"
        match = re.search(pattern, text)
        if match:
            candidate = _extract_knowledge_title(match.group(1))
            if candidate:
                return candidate
    return ""


def _session_knowledge_title(profile_like: Optional[dict], fallback: Any = "") -> str:
    profile_like = profile_like or {}
    summary_candidates = [
        _extract_segment_by_labels(profile_like.get("profile_summary"), ["薄弱知识点", "薄弱点", "易错点", "当前难点"]),
        _extract_segment_by_labels(profile_like.get("profile_summary"), ["当前学习主题", "学习主题", "当前聚焦"]),
    ]
    for title in summary_candidates:
        if title:
            return title[:120]

    candidate_fields = [
        "weak_knowledge_points",
        "current_difficulty",
        "current_topic",
        "recent_progress",
        "course_progress",
        "profile_summary",
        "target_course",
        "major",
    ]
    for field in candidate_fields:
        title = _extract_knowledge_title(profile_like.get(field))
        if title:
            return title[:120]

    fallback_title = _extract_knowledge_title(fallback) or _normalize_text(fallback)
    return (fallback_title or "新对话")[:120]


def _conversation_evidence_snapshot(user_id: int, limit_sessions: int = 8, limit_messages: int = 24) -> list[dict]:
    rows = mysql_db.query_all(
        """
        SELECT ps.id, ps.title, ps.create_time, pc.messages
        FROM profile_session ps
        LEFT JOIN profile_conversation pc
          ON pc.user_id = ps.user_id AND pc.profile_session_id = ps.id
        WHERE ps.user_id=%s
        ORDER BY ps.update_time DESC, ps.id DESC
        LIMIT %s
        """,
        (user_id, limit_sessions),
    )
    result = []
    for row in rows:
        messages = _json_loads(row.get("messages"), [])
        compact_messages = []
        if isinstance(messages, list):
            for item in messages[-limit_messages:]:
                role = "学生" if item.get("role") == "user" else "助手"
                content = _trim_text(item.get("content"), 140)
                if content:
                    compact_messages.append({"role": role, "content": content})
        result.append(
            {
                "session_id": row.get("id"),
                "title": _trim_text(row.get("title"), 80),
                "create_time": str(row.get("create_time") or ""),
                "messages": compact_messages,
            }
        )
    return result


def _portrait_score_fallback(profile: dict, evidence: dict) -> dict:
    dimensions = {}
    for key, label in DIMENSION_LABELS.items():
        filled = bool(_normalize_text(profile.get(key)))
        score = 50 if filled else 35
        dimensions[key] = {
            "score": score,
            "level": _score_level(score),
            "reason": f"{label}本轮暂未完成模型评估，当前展示为系统兜底结果。",
        }
    return {
        "dimensions": dimensions,
        "overall_score": round(sum(item["score"] for item in dimensions.values()) / max(len(dimensions), 1), 1),
        "completion_ratio": round(len([k for k in CORE_PROFILE_DIMENSIONS if _normalize_text(profile.get(k))]) / max(len(CORE_PROFILE_DIMENSIONS), 1), 2),
        "confidence_label": "低",
        "evidence": evidence,
        "method": "大模型评分暂未成功返回，当前为系统兜底展示。",
        "evidence_summary": "本次画像评分未获得有效模型输出。",
        "teacher_summary": "当前画像评分暂未成功生成，建议先继续补充对话，再重新获取更稳定的教师式评估。",
        "overall_comment": "先继续补充学习情况与真实困惑，再进行画像评估会更准确。",
    }


def _build_portrait_scoring_evidence(user_id: int, profile: dict) -> dict:
    quiz_rows = mysql_db.query_all(
        "SELECT score, knowledge_point, create_time FROM quiz_result WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )
    mastery_rows = mysql_db.query_all(
        "SELECT knowledge_point, mastery_score, weak_reason FROM mastery_record WHERE user_id=%s ORDER BY update_time DESC LIMIT 50",
        (user_id,),
    )
    event_rows = mysql_db.query_all(
        "SELECT event_type, knowledge_point, detail, create_time FROM learning_event WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )
    resource_feedback_rows = mysql_db.query_all(
        "SELECT rating, comment, create_time FROM resource_feedback WHERE user_id=%s ORDER BY create_time DESC LIMIT 30",
        (user_id,),
    )
    resource_rows = mysql_db.query_all(
        "SELECT resource_type, title, create_time FROM study_resource WHERE user_id=%s ORDER BY create_time DESC LIMIT 50",
        (user_id,),
    )

    quiz_scores = [_safe_int(item.get("score"), 0) for item in quiz_rows]
    mastery_scores = [_safe_int(item.get("mastery_score"), 0) for item in mastery_rows]

    return {
        "profile_snapshot": {
            "major": _trim_text(profile.get("major"), 80),
            "target_course": _trim_text(profile.get("target_course"), 80),
            "current_topic": _trim_text(profile.get("current_topic"), 160),
            "mastery_level": _trim_text(profile.get("mastery_level"), 120),
            "current_difficulty": _trim_text(profile.get("current_difficulty"), 160),
            "task_goal": _trim_text(profile.get("task_goal"), 160),
            "support_preference": _trim_text(profile.get("support_preference"), 120),
            "engagement_level": _trim_text(profile.get("engagement_level"), 120),
            "learning_background": _trim_text(profile.get("learning_background"), 160),
            "recent_progress": _trim_text(profile.get("recent_progress"), 160),
            "schedule_pattern": _trim_text(profile.get("schedule_pattern"), 120),
            "preferred_resource": _trim_text(profile.get("preferred_resource"), 120),
            "weak_knowledge_points": _trim_text(profile.get("weak_knowledge_points"), 200),
            "recommended_next_step": _trim_text(profile.get("recommended_next_step"), 200),
            "profile_summary": _trim_text(profile.get("profile_summary"), 200),
        },
        "conversation_sessions": _conversation_evidence_snapshot(user_id),
        "quiz_summary": {
            "count": len(quiz_rows),
            "avg_score": round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else 0,
            "items": [
                {
                    "knowledge_point": _trim_text(item.get("knowledge_point"), 80),
                    "score": _safe_int(item.get("score"), 0),
                    "time": str(item.get("create_time") or ""),
                }
                for item in quiz_rows[:12]
            ],
        },
        "mastery_summary": {
            "count": len(mastery_rows),
            "avg_mastery": round(sum(mastery_scores) / len(mastery_scores), 1) if mastery_scores else 0,
            "items": [
                {
                    "knowledge_point": _trim_text(item.get("knowledge_point"), 80),
                    "mastery_score": _safe_int(item.get("mastery_score"), 0),
                    "weak_reason": _trim_text(item.get("weak_reason"), 120),
                }
                for item in mastery_rows[:15]
            ],
        },
        "learning_events": [
            {
                "event_type": _trim_text(item.get("event_type"), 40),
                "knowledge_point": _trim_text(item.get("knowledge_point"), 80),
                "detail": _trim_text(item.get("detail"), 120),
                "time": str(item.get("create_time") or ""),
            }
            for item in event_rows[:15]
        ],
        "resource_feedback": [
            {
                "rating": _safe_int(item.get("rating"), 0),
                "comment": _trim_text(item.get("comment"), 120),
                "time": str(item.get("create_time") or ""),
            }
            for item in resource_feedback_rows[:12]
        ],
        "resource_usage": [
            {
                "resource_type": _trim_text(item.get("resource_type"), 40),
                "title": _trim_text(item.get("title"), 80),
                "time": str(item.get("create_time") or ""),
            }
            for item in resource_rows[:15]
        ],
        "counts": {
            "session_count": len(_conversation_evidence_snapshot(user_id)),
            "quiz_count": len(quiz_rows),
            "mastery_count": len(mastery_rows),
            "event_count": len(event_rows),
            "resource_feedback_count": len(resource_feedback_rows),
            "resource_count": len(resource_rows),
        },
    }


def _portrait_dimension_scores(user_id: int, profile: dict) -> dict:
    evidence = _build_portrait_scoring_evidence(user_id, profile)

    if not profile or config.MOCK_AI:
        return _portrait_score_fallback(profile, evidence)

    try:
        prompt = PORTRAIT_SCORE_PROMPT_TEMPLATE.format(
            profile_json=json.dumps(profile, ensure_ascii=False, indent=2),
            evidence_json=json.dumps(evidence, ensure_ascii=False, indent=2),
        )
        raw = PlatformLLM().invoke(prompt)
        data = parse_json_with_fallback(raw)
        dimensions_raw = data.get("dimensions") if isinstance(data, dict) else {}

        dimensions = {}
        for key in CORE_PROFILE_DIMENSIONS:
            item = dimensions_raw.get(key) if isinstance(dimensions_raw, dict) else {}
            score = _clamp_score(_safe_int(item.get("score"), 0))
            level = str(item.get("level") or _score_level(score)).strip() or _score_level(score)
            teacher_judgement = str(item.get("teacher_judgement") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if teacher_judgement and reason:
                merged_reason = f"{teacher_judgement}；{reason}"
            else:
                merged_reason = teacher_judgement or reason or f"{DIMENSION_LABELS[key]}当前仍需更多学习证据支撑。"
            dimensions[key] = {
                "score": score,
                "level": level,
                "teacher_judgement": teacher_judgement,
                "reason": merged_reason,
            }

        if not dimensions:
            return _portrait_score_fallback(profile, evidence)

        filled_core_count = len([key for key in CORE_PROFILE_DIMENSIONS if _normalize_text(profile.get(key))])
        overall_score = round(
            _safe_float(data.get("overall_score"), sum(item["score"] for item in dimensions.values()) / max(len(dimensions), 1)),
            1,
        )
        completion_ratio = round(
            _safe_float(
                data.get("completion_ratio"),
                filled_core_count / max(len(CORE_PROFILE_DIMENSIONS), 1),
            ),
            2,
        )
        completion_ratio = max(0.0, min(1.0, completion_ratio))

        return {
            "dimensions": dimensions,
            "overall_score": overall_score,
            "completion_ratio": completion_ratio,
            "confidence_label": str(data.get("confidence_label") or profile.get("portrait_confidence") or "中").strip() or "中",
            "evidence": evidence,
            "method": str(data.get("method") or "基于多轮对话、学习记录和评估证据的大模型综合评分").strip(),
            "evidence_summary": str(data.get("evidence_summary") or "").strip(),
            "teacher_summary": str(data.get("teacher_summary") or "").strip(),
            "overall_comment": str(data.get("overall_comment") or "").strip(),
        }
    except Exception:
        return _portrait_score_fallback(profile, evidence)


def _latest_portrait_snapshot(user_id: int) -> dict:
    row = mysql_db.query_one(
        """
        SELECT id, profile_summary, portrait_scoring, profile_snapshot, create_time
        FROM portrait_snapshot
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    return row or {}


def _cached_portrait_scoring(user_id: int, profile: dict) -> Optional[dict]:
    latest = _latest_portrait_snapshot(user_id)
    scoring = _json_loads(latest.get("portrait_scoring"), {})
    if not isinstance(scoring, dict) or not scoring.get("dimensions"):
        return None

    cached_snapshot = _json_loads(latest.get("profile_snapshot"), {})
    current_snapshot = _snapshot_profile_view(profile or {})
    if cached_snapshot == current_snapshot:
        scoring["method"] = scoring.get("method") or "读取最近一次画像评分缓存"
        return scoring
    return None


def _aggregate_profile_payload(user_id: int, profile: dict, refresh_scoring: bool = False) -> dict:
    payload = dict(profile or {})
    if refresh_scoring:
        payload["portrait_scoring"] = _portrait_dimension_scores(user_id, payload)
    else:
        cached_scoring = _cached_portrait_scoring(user_id, payload)
        payload["portrait_scoring"] = cached_scoring or _portrait_score_fallback(payload, {})
    payload["portrait_history"] = _portrait_history(user_id, limit=6)
    return payload


def _snapshot_profile_view(profile: dict) -> dict:
    return {
        "major": _trim_text(profile.get("major"), 80),
        "target_course": _trim_text(profile.get("target_course"), 80),
        "current_topic": _trim_text(profile.get("current_topic"), 120),
        "mastery_level": _trim_text(profile.get("mastery_level"), 120),
        "current_difficulty": _trim_text(profile.get("current_difficulty"), 120),
        "task_goal": _trim_text(profile.get("task_goal"), 160),
        "support_preference": _trim_text(profile.get("support_preference"), 120),
        "engagement_level": _trim_text(profile.get("engagement_level"), 120),
        "profile_summary": _trim_text(profile.get("profile_summary"), 240),
    }


def _snapshot_dimension_signature(portrait_scoring: dict) -> dict:
    dimensions = portrait_scoring.get("dimensions") if isinstance(portrait_scoring, dict) else {}
    result = {}
    if not isinstance(dimensions, dict):
        return result
    for key in CORE_PROFILE_DIMENSIONS:
        item = dimensions.get(key) or {}
        result[key] = {
            "score": _safe_int(item.get("score"), 0),
            "level": str(item.get("level") or "").strip(),
            "reason": str(item.get("reason") or "").strip(),
        }
    return result


def _persist_portrait_snapshot(
    user_id: int,
    profile_session_id: int,
    profile: dict,
    portrait_scoring: dict,
    trigger_source: str = "profile_update",
    force: bool = False,
) -> None:
    try:
        latest = mysql_db.query_one(
            """
            SELECT id, profile_summary, portrait_scoring
            FROM portrait_snapshot
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ) or {}
        latest_scoring = _json_loads(latest.get("portrait_scoring"), {})
        latest_signature = _snapshot_dimension_signature(latest_scoring)
        current_signature = _snapshot_dimension_signature(portrait_scoring)
        current_summary = _trim_text(profile.get("profile_summary"), 240)

        if (not force) and latest and latest_signature == current_signature and _trim_text(latest.get("profile_summary"), 240) == current_summary:
            return

        mysql_db.insert(
            "portrait_snapshot",
            {
                "user_id": user_id,
                "profile_session_id": profile_session_id,
                "trigger_source": trigger_source[:64],
                "profile_summary": current_summary or None,
                "portrait_scoring": _json_dumps(portrait_scoring),
                "profile_snapshot": _json_dumps(_snapshot_profile_view(profile)),
            },
        )
    except Exception:
        return


def _portrait_history(user_id: int, limit: int = 6) -> list[dict]:
    rows = mysql_db.query_all(
        """
        SELECT id, profile_session_id, trigger_source, profile_summary, portrait_scoring, profile_snapshot, create_time
        FROM portrait_snapshot
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
    result = []
    for row in rows:
        result.append(
            {
                "id": row.get("id"),
                "profile_session_id": row.get("profile_session_id"),
                "trigger_source": row.get("trigger_source") or "profile_update",
                "profile_summary": _trim_text(row.get("profile_summary"), 240),
                "portrait_scoring": _json_loads(row.get("portrait_scoring"), {}),
                "profile_snapshot": _json_loads(row.get("profile_snapshot"), {}),
                "create_time": str(row.get("create_time") or ""),
            }
        )
    return result


@profile_bp.get("/user-info")
@login_required
def get_user_info():
    try:
        return success(_user_personal_info(request.user_id), "个人信息读取成功")
    except Exception as exc:
        if _is_missing_schema_error(exc):
            return success({"major": "", "target_course": "", "education_level": "", "school": ""}, "个人信息表字段尚未初始化")
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
            SELECT ps.*, sp.profile_summary, sp.major, sp.target_course, sp.current_topic, sp.current_difficulty,
                   sp.weak_knowledge_points, sp.recent_progress, sp.course_progress, sp.update_time AS profile_update_time,
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
            desired_title = _session_knowledge_title(row, row.get("title"))
            if desired_title and desired_title != row.get("title"):
                mysql_db.update("profile_session", {"title": desired_title}, "id=%s AND user_id=%s", (row["id"], request.user_id))
                row["title"] = desired_title
        return success({"sessions": rows, "active_session_id": session["id"] if session else None}, "查询成功")
    except Exception as exc:
        if _is_missing_schema_error(exc):
            return success({"sessions": [], "active_session_id": None}, "画像会话表尚未初始化")
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

        title = _session_knowledge_title(data, session.get("title"))
        mysql_db.update("profile_session", {"title": str(title)[:120]}, "id=%s AND user_id=%s", (session_id, request.user_id))

        conversation = payload.get("conversation")
        if isinstance(conversation, dict):
            _save_conversation_payload(request.user_id, session_id, conversation)

        _delete_session_outputs(request.user_id, session_id)
        aggregate_profile = _aggregate_profile_payload(
            request.user_id,
            _refresh_aggregate_profile(request.user_id, transient_profile=profile),
            refresh_scoring=True,
        )
        _persist_portrait_snapshot(
            user_id=request.user_id,
            profile_session_id=session_id,
            profile=aggregate_profile,
            portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
            trigger_source="create_profile",
            force=True,
        )
        aggregate_profile["portrait_history"] = _portrait_history(request.user_id, limit=6)
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
            refresh_scoring=True,
        )
        _persist_portrait_snapshot(
            user_id=request.user_id,
            profile_session_id=session_id,
            profile=aggregate_profile,
            portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
            trigger_source="update_profile",
            force=True,
        )
        aggregate_profile["portrait_history"] = _portrait_history(request.user_id, limit=6)
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
        profile = _merge_personal_info(profile or _empty_profile(), _user_personal_info(request.user_id))
        payload = _aggregate_profile_payload(request.user_id, profile, refresh_scoring=False)
        return success(payload, "综合画像读取成功")
    except Exception as exc:
        if _is_missing_schema_error(exc):
            data = _empty_profile()
            data["portrait_scoring"] = _portrait_score_fallback(data, {})
            data["portrait_history"] = []
            return success(data, "综合画像表尚未初始化")
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
        if _is_missing_schema_error(exc):
            return success({}, "对话记录表尚未初始化")
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
