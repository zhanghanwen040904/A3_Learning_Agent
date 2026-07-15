import json
import re
from datetime import date, datetime, timedelta
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
    "knowledge_foundation",
    "knowledge_mastery",
    "weak_point_distribution",
    "learning_progress",
    "engagement_level",
    "support_match",
    "error_pattern_stability",
    "goal_attainment_risk",
]

DEFAULT_VALUE = "待进一步观察"
AGGREGATE_PROFILE_SESSION_ID = 0
DIMENSION_LABELS = {
    "knowledge_foundation": "知识基础",
    "knowledge_mastery": "知识点掌握",
    "weak_point_distribution": "薄弱点分布",
    "learning_progress": "学习进度",
    "engagement_level": "学习投入",
    "support_match": "支持方式匹配",
    "error_pattern_stability": "易错类型稳定性",
    "goal_attainment_risk": "目标达成把握",
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
- knowledge_foundation：学生在本课程上的起点基础。分高表示前置概念较稳，不是完全依赖外部扶着走。
- knowledge_mastery：学生对当前学习章节和已接触知识点的真实掌握程度。分高表示能理解、能做题、能迁移。
- weak_point_load：当前薄弱知识点带来的学习压力。注意这里分高表示薄弱点压力较小、可控；分低表示薄弱点多且集中。
- learning_progress：学生的学习推进状态。分高表示阶段清晰、学习路径持续前进，而不是停留在同一困惑上。
- engagement_level：学生投入度、持续性和主动性。分高表示学习意愿稳定、互动积极、最近有持续学习行为。
- support_match：系统当前给出的帮助方式与学生需求是否匹配。分高表示已经能判断出学生更适合哪类支持，且支持方向较有效。

请输出严格符合以下 JSON 结构：
{{
  "teacher_summary": "",
  "overall_comment": "",
  "dimensions": {{
    "knowledge_foundation": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "knowledge_mastery": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "weak_point_load": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "learning_progress": {{
      "score": 0,
      "level": "低",
      "teacher_judgement": "",
      "reason": ""
    }},
    "support_match": {{
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


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _clamp_percent(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _saturating_count_score(count: int, max_count: int, max_score: int) -> int:
    if max_count <= 0 or max_score <= 0:
        return 0
    safe_count = max(0, min(int(count), int(max_count)))
    ratio = safe_count / max_count
    return _clamp_percent(max_score * (1 - (1 - ratio) ** 2))


def _cap_with_excellence_gate(score: int, soft_cap: int, hard_cap: int, conditions: list[bool]) -> int:
    safe_score = _clamp_percent(score)
    if all(conditions):
        return min(safe_score, hard_cap)
    return min(safe_score, soft_cap)


def _score_band_text(score: int) -> str:
    if score >= 85:
        return "较强"
    if score >= 70:
        return "稳定提升"
    if score >= 55:
        return "建立中"
    return "需重点支持"


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
    dynamic = _derive_learning_profile(profile, evidence)
    dynamic_scores = dynamic.get("dynamic_scores") or {}
    dimensions = {}
    for key, label in DIMENSION_LABELS.items():
        score = _safe_int(dynamic_scores.get(key), 45)
        dynamic_value = _trim_text(dynamic.get(key), 120)
        dimensions[key] = {
            "score": score,
            "level": _score_level(score),
            "teacher_judgement": dynamic_value or f"{label}已根据近期学习证据完成判断",
            "reason": (dynamic.get("score_details") or {}).get(key) or f"{label}当前基于答题、掌握度、错题和学习行为自动生成；后续继续学习后会持续修正该维度。",
        }
    return {
        "dimensions": dimensions,
        "overall_score": round(sum(item["score"] for item in dimensions.values()) / max(len(dimensions), 1), 1),
        "completion_ratio": round(len([k for k in CORE_PROFILE_DIMENSIONS if _safe_int(dynamic_scores.get(k), 0) > 0]) / max(len(CORE_PROFILE_DIMENSIONS), 1), 2),
        "confidence_label": "中",
        "evidence": evidence,
        "method": "当前按学习证据规则生成动态画像，若大模型评分返回成功会进一步细化教师评语。",
        "evidence_summary": f"已读取对话、练习、掌握度、错题与资源行为证据；当前综合掌握约 {dynamic.get('overall_mastery_score', 0)} 分。",
        "teacher_summary": f"系统已根据学习记录形成动态画像：当前学习阶段为“{dynamic.get('current_stage_label', '待观察')}”，薄弱知识点主要集中在“{dynamic.get('weak_knowledge_points', DEFAULT_VALUE)}”。",
        "overall_comment": dynamic.get("goal_risk") or "建议继续围绕薄弱知识点完成练习、反馈和再次验证。",
        "dynamic_profile": dynamic,
    }

def _parse_learning_time(value):
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _build_learning_effect_overview(quiz_rows: list, event_rows: list, resource_usage_items: list) -> dict:
    today = date.today()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    daily = {
        item: {"duration_sec": 0, "completed_tasks": 0, "quiz_scores": [], "event_count": 0}
        for item in days
    }

    total_duration_sec = 0
    completed_resources = 0
    progress_values = []
    for item in resource_usage_items:
        duration = max(0, _safe_int(item.get("duration_sec"), 0))
        progress = max(0, min(100, _safe_int(item.get("progress"), 0)))
        completed = bool(item.get("completed")) or progress >= 100
        occurred_at = _parse_learning_time(item.get("time"))
        if occurred_at and occurred_at.date() in daily:
            total_duration_sec += duration
            progress_values.append(progress)
            completed_resources += int(completed)
            daily[occurred_at.date()]["duration_sec"] += duration
            daily[occurred_at.date()]["completed_tasks"] += int(completed)

    stage_states = {}
    for item in event_rows:
        occurred_at = _parse_learning_time(item.get("create_time"))
        event_type = str(item.get("event_type") or "").strip()
        detail = _json_loads(item.get("detail"), {})
        if event_type == "complete_stage":
            stage_key = detail.get("stage_index") if isinstance(detail, dict) else None
            path_key = detail.get("path_id") if isinstance(detail, dict) else None
            state_key = (str(item.get("profile_session_id") or ""), str(path_key or ""), str(stage_key or ""))
            if state_key not in stage_states:
                stage_states[state_key] = {
                    "completed": bool(detail.get("completed", True)) if isinstance(detail, dict) else True,
                    "time": occurred_at,
                }
        if occurred_at and occurred_at.date() in daily and event_type != "resource_usage":
            daily[occurred_at.date()]["event_count"] += 1

    completed_stages = set()
    for state_key, state in stage_states.items():
        occurred_at = state.get("time")
        if not state.get("completed") or not occurred_at or occurred_at.date() not in daily:
            continue
        completed_stages.add(state_key)
        daily[occurred_at.date()]["completed_tasks"] += 1

    quiz_scores = []
    for item in quiz_rows:
        score = max(0, min(100, _safe_int(item.get("score"), 0)))
        occurred_at = _parse_learning_time(item.get("create_time"))
        if occurred_at and occurred_at.date() in daily:
            quiz_scores.append(score)
            daily[occurred_at.date()]["quiz_scores"].append(score)

    trend = []
    for day_value in days:
        item = daily[day_value]
        avg_score = round(sum(item["quiz_scores"]) / len(item["quiz_scores"]), 1) if item["quiz_scores"] else 0
        duration_score = min(45, round(item["duration_sec"] / 120))
        completion_score = min(25, item["completed_tasks"] * 10)
        activity_score = min(15, item["event_count"] * 3)
        quiz_score = round(avg_score * 0.15) if item["quiz_scores"] else 0
        trend.append(
            {
                "date": day_value.strftime("%m/%d"),
                "activity_score": min(100, duration_score + completion_score + activity_score + quiz_score),
                "duration_sec": item["duration_sec"],
                "completed_tasks": item["completed_tasks"],
                "avg_score": avg_score,
            }
        )

    return {
        "period": f"{days[0].strftime('%m/%d')} - {days[-1].strftime('%m/%d')}",
        "total_duration_sec": total_duration_sec,
        "completed_tasks": completed_resources + len(completed_stages),
        "task_completion_rate": round(sum(progress_values) / len(progress_values)) if progress_values else 0,
        "correct_rate": round(sum(quiz_scores) / len(quiz_scores)) if quiz_scores else 0,
        "quiz_count": len(quiz_scores),
        "trend": trend,
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
        "SELECT id, profile_session_id, event_type, knowledge_point, detail, create_time FROM learning_event WHERE user_id=%s ORDER BY create_time DESC, id DESC LIMIT 50",
        (user_id,),
    )
    resource_feedback_rows = mysql_db.query_all(
        "SELECT rating, comment, create_time FROM resource_feedback WHERE user_id=%s ORDER BY create_time DESC LIMIT 30",
        (user_id,),
    )
    resource_usage_rows = mysql_db.query_all(
        """
        SELECT detail, create_time
        FROM learning_event
        WHERE user_id=%s AND event_type='resource_usage'
        ORDER BY create_time DESC, id DESC
        LIMIT 50
        """,
        (user_id,),
    )
    wrong_book_rows = mysql_db.query_all(
        """
        SELECT question, knowledge_point, score, feedback, common_mistake, create_time
        FROM quiz_wrong_book
        WHERE user_id=%s
        ORDER BY create_time DESC, id DESC
        LIMIT 50
        """,
        (user_id,),
    )

    quiz_scores = [_safe_int(item.get("score"), 0) for item in quiz_rows]
    mastery_scores = [_safe_int(item.get("mastery_score"), 0) for item in mastery_rows]

    resource_usage_by_id = {}
    for item in resource_usage_rows:
        detail = _json_loads(item.get("detail"), {})
        if not isinstance(detail, dict):
            detail = {}
        resource_id = str(detail.get("resource_id") or f"{detail.get('resource_type')}:{detail.get('title')}")
        current = resource_usage_by_id.setdefault(
            resource_id,
            {
                "resource_id": detail.get("resource_id"),
                "resource_type": _trim_text(detail.get("resource_type"), 40),
                "title": _trim_text(detail.get("title"), 80),
                "progress": 0,
                "duration_sec": 0,
                "completed": False,
                "time": str(item.get("create_time") or ""),
            },
        )
        current["duration_sec"] += max(0, _safe_int(detail.get("duration_sec"), 0))
        current["progress"] = max(current["progress"], _safe_int(detail.get("progress"), 0))
        current["completed"] = current["completed"] or bool(detail.get("completed"))

    resource_usage_items = list(resource_usage_by_id.values())

    learning_effect_overview = _build_learning_effect_overview(quiz_rows, event_rows, resource_usage_items)

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
        "resource_usage": resource_usage_items[:50],
        "learning_effect_overview": learning_effect_overview,
        "wrong_book": [
            {
                "knowledge_point": _trim_text(item.get("knowledge_point"), 80),
                "score": _safe_int(item.get("score"), 0),
                "feedback": _trim_text(item.get("feedback"), 120),
                "common_mistake": _trim_text(item.get("common_mistake"), 120),
                "question": _trim_text(item.get("question"), 120),
                "time": str(item.get("create_time") or ""),
            }
            for item in wrong_book_rows[:15]
        ],
        "counts": {
            "session_count": len(_conversation_evidence_snapshot(user_id)),
            "quiz_count": len(quiz_rows),
            "mastery_count": len(mastery_rows),
            "event_count": len(event_rows),
            "resource_feedback_count": len(resource_feedback_rows),
            "resource_count": len(resource_usage_items),
            "wrong_book_count": len(wrong_book_rows),
        },
    }

def _derive_learning_profile(profile: dict, evidence: dict) -> dict:
    quiz_items = ((evidence or {}).get("quiz_summary") or {}).get("items") or []
    mastery_items = ((evidence or {}).get("mastery_summary") or {}).get("items") or []
    learning_events = (evidence or {}).get("learning_events") or []
    resource_feedback = (evidence or {}).get("resource_feedback") or []
    resource_usage = (evidence or {}).get("resource_usage") or []
    wrong_book = (evidence or {}).get("wrong_book") or []

    avg_quiz = _safe_float(((evidence or {}).get("quiz_summary") or {}).get("avg_score"), 0.0)
    avg_mastery = _safe_float(((evidence or {}).get("mastery_summary") or {}).get("avg_mastery"), 0.0)
    quiz_count = len(quiz_items)
    event_count = len(learning_events)
    resource_count = len(resource_usage)
    wrong_book_count = len(wrong_book)
    stage_complete_events = [item for item in learning_events if str(item.get("event_type") or "") == "complete_stage"]
    stage_complete_count = len(stage_complete_events)
    conversation_message_count = sum(
        1
        for item in ((evidence or {}).get("conversation_sessions") or [])
        if isinstance(item, dict)
        for message in (item.get("messages") or [])
        if isinstance(message, dict)
        and str(message.get("role") or "").strip().lower() in {"user", "student", "学生", "我"}
    )
    has_observation_evidence = any(
        [
            conversation_message_count,
            quiz_count,
            len(mastery_items),
            event_count,
            len(resource_feedback),
            resource_count,
            wrong_book_count,
        ]
    )

    weak_points = [item for item in mastery_items if _safe_int(item.get("mastery_score"), 0) < 70]
    strong_points = [item for item in mastery_items if _safe_int(item.get("mastery_score"), 0) >= 85]
    weak_count = len(weak_points)
    strong_count = len(strong_points)

    current_topic = _trim_text(profile.get("current_topic"), 160)
    weak_summary = "、".join(
        item.get("knowledge_point") for item in weak_points[:5] if _trim_text(item.get("knowledge_point"), 80)
    ) or _trim_text(profile.get("weak_knowledge_points"), 200)
    strong_summary = "、".join(
        item.get("knowledge_point") for item in strong_points[:5] if _trim_text(item.get("knowledge_point"), 80)
    )

    foundation_score = _clamp_percent(
        0.55 * avg_mastery
        + 0.15 * avg_quiz
        + 10 * (1 if _normalize_text(profile.get("learning_background")) else 0)
        + 8 * (1 if _normalize_text(profile.get("major")) else 0)
    )
    mastery_score = _clamp_percent(0.65 * avg_mastery + 0.35 * avg_quiz)
    weak_distribution_score = _clamp_percent(
        100
        - min(weak_count, 6) * 9
        - min(wrong_book_count, 8) * 4
        - max(0, 70 - avg_mastery) * 0.35
    )
    progress_raw_score = _clamp_percent(
        0.35 * mastery_score
        + _saturating_count_score(strong_count, 4, 24)
        + _saturating_count_score(stage_complete_count, 4, 18)
        + _saturating_count_score(quiz_count, 6, 16)
        + _saturating_count_score(resource_count, 5, 10)
        + 10 * (1 if current_topic else 0)
        - min(weak_count, 5) * 2
    )
    engagement_raw_score = _clamp_percent(
        22
        + _saturating_count_score(event_count, 6, 24)
        + _saturating_count_score(quiz_count, 5, 18)
        + _saturating_count_score(resource_count, 5, 12)
        + 8 * (1 if _normalize_text(profile.get("engagement_level")) else 0)
        - min(wrong_book_count, 6) * 2
    )
    progress_score = _cap_with_excellence_gate(
        progress_raw_score,
        92,
        100,
        [
            mastery_score >= 85,
            weak_count <= 1,
            strong_count >= 2,
            stage_complete_count >= 1,
            quiz_count >= 5,
            resource_count >= 3,
            bool(current_topic),
        ],
    )
    engagement_score = _cap_with_excellence_gate(
        engagement_raw_score,
        90,
        100,
        [
            mastery_score >= 80,
            wrong_book_count <= 2,
            event_count >= 4,
            quiz_count >= 4,
            resource_count >= 3,
            _normalize_text(profile.get("engagement_level")) != "",
        ],
    )
    avg_feedback = round(
        sum(_safe_int(item.get("rating"), 0) for item in resource_feedback) / len(resource_feedback),
        1,
    ) if resource_feedback else 0.0
    support_match_raw_score = _clamp_percent(
        26
        + 24 * (1 if _normalize_text(profile.get("support_preference")) else 0)
        + 18 * (1 if _normalize_text(profile.get("preferred_resource")) else 0)
        + 6 * avg_feedback
        + _saturating_count_score(len(resource_feedback), 4, 8)
    )
    support_match_score = _cap_with_excellence_gate(
        support_match_raw_score,
        93,
        100,
        [
            avg_feedback >= 4.5,
            len(resource_feedback) >= 3,
            resource_count >= 3,
            _normalize_text(profile.get("support_preference")) != "",
            _normalize_text(profile.get("preferred_resource")) != "",
            mastery_score >= 78,
        ],
    )

    common_mistake_text = " ".join(
        part for part in [
            " ".join(_trim_text(item.get("common_mistake"), 120) for item in wrong_book),
            " ".join(_trim_text(item.get("feedback"), 120) for item in wrong_book),
            " ".join(_trim_text(item.get("detail"), 120) for item in learning_events),
        ] if part
    )

    stage_label = current_topic or _trim_text(profile.get("recent_progress"), 160) or "课程起步阶段"

    error_pattern = DEFAULT_VALUE
    error_pattern_score = 58
    if any(keyword in common_mistake_text for keyword in ["概念", "定义", "理解"]):
        error_pattern = "概念理解型错误偏多"
        error_pattern_score = 60 if wrong_book_count >= 3 else 68
    elif any(keyword in common_mistake_text for keyword in ["步骤", "流程", "顺序"]):
        error_pattern = "步骤遗漏型错误偏多"
        error_pattern_score = 62 if wrong_book_count >= 3 else 70
    elif any(keyword in common_mistake_text for keyword in ["计算", "公式", "推导"]):
        error_pattern = "公式推导或计算型错误偏多"
        error_pattern_score = 61 if wrong_book_count >= 3 else 69
    elif weak_summary and weak_summary != DEFAULT_VALUE:
        error_pattern = "错误主要集中在当前薄弱知识点"
        error_pattern_score = 72 if weak_count <= 2 else 64
    error_pattern_score = _clamp_percent(error_pattern_score + max(0, 3 - min(wrong_book_count, 3)) * 6)

    knowledge_map = []
    for item in mastery_items[:20]:
        score = _safe_int(item.get("mastery_score"), 0)
        knowledge_map.append(
            {
                "knowledge_point": _trim_text(item.get("knowledge_point"), 80),
                "mastery_score": score,
                "status": "薄弱" if score < 70 else "稳定" if score < 85 else "较好",
                "weak_reason": _trim_text(item.get("weak_reason"), 120),
                "trend": "up" if score >= 70 else "down",
            }
        )

    goal_text = _trim_text(profile.get("task_goal"), 160)
    goal_risk = DEFAULT_VALUE
    goal_risk_score = 55
    target_match = re.search(r"(\d{2,3})\s*[分%]?", goal_text)
    if target_match:
        target = _safe_int(target_match.group(1), 0)
        current = mastery_score or foundation_score
        gap = max(0, target - current)
        if gap <= 8:
            goal_risk = "目标达成把握较高"
            goal_risk_score = 88
        elif gap <= 20:
            goal_risk = "目标可以达成，但还需要持续补弱"
            goal_risk_score = 72
        else:
            goal_risk = "目标存在明显压力，需要先补齐关键薄弱点"
            goal_risk_score = 54
    elif goal_text:
        goal_risk = "已有目标方向，但尚未量化到可跟踪标准"
        goal_risk_score = 66

    # A newly registered user has no observable learning evidence. Baseline constants
    # must not be presented as measured ability, otherwise the portrait is misleading.
    if not has_observation_evidence:
        foundation_score = 0
        mastery_score = 0
        weak_distribution_score = 0
        progress_raw_score = 0
        progress_score = 0
        engagement_raw_score = 0
        engagement_score = 0
        support_match_raw_score = 0
        support_match_score = 0
        error_pattern_score = 0
        goal_risk_score = 0
        stage_label = "待进一步观察"
        weak_summary = DEFAULT_VALUE
        strong_summary = DEFAULT_VALUE
        error_pattern = DEFAULT_VALUE
        goal_risk = DEFAULT_VALUE

    score_details = {
        "knowledge_foundation": f"知识基础 = 55%掌握度({avg_mastery:.1f}) + 15%答题均分({avg_quiz:.1f}) + 背景识别加分 + 专业识别加分，当前为 {foundation_score} 分。",
        "knowledge_mastery": f"知识点掌握 = 65%掌握度({avg_mastery:.1f}) + 35%答题均分({avg_quiz:.1f})，当前为 {mastery_score} 分。",
        "weak_point_distribution": f"薄弱点分布从 100 分起，根据薄弱知识点数({weak_count})、错题数({wrong_book_count}) 和掌握度不足部分扣分，当前为 {weak_distribution_score} 分。",
        "learning_progress": f"学习进度 = 35%掌握质量 + 强项知识点({strong_count}) + 阶段完成数({stage_complete_count}) + 答题记录({quiz_count}) + 资源学习({resource_count}) + 当前主题识别，并对薄弱点数做小幅扣分。未满足卓越门槛时最高 92 分；当前原始分 {progress_raw_score}，展示分 {progress_score}。",
        "engagement_level": f"学习投入 = 基础分 + 学习事件({event_count}) + 答题记录({quiz_count}) + 资源学习({resource_count}) + 投入状态识别，并对错题积压做小幅扣分。未满足卓越门槛时最高 90 分；当前原始分 {engagement_raw_score}，展示分 {engagement_score}。",
        "support_match": f"支持方式匹配 = 基础分 + 支持偏好识别 + 资源偏好识别 + 资源反馈均分({avg_feedback:.1f}) + 反馈次数修正。未满足卓越门槛时最高 93 分；当前原始分 {support_match_raw_score}，展示分 {support_match_score}。",
        "error_pattern_stability": f"易错类型稳定性根据错题与反馈文本中的错误模式关键词判断，结合错题数量({wrong_book_count})修正，当前为 {error_pattern_score} 分。",
        "goal_attainment_risk": f"目标达成把握根据任务目标文本是否量化以及目标与当前掌握度的差距判断，当前为 {goal_risk_score} 分。",
    }
    if not has_observation_evidence:
        score_details = {
            key: f"{label}尚无对话、练习、资源学习或反馈证据，暂不评分；完成首次真实学习行为后将自动更新。"
            for key, label in DIMENSION_LABELS.items()
        }

    return {
        "knowledge_foundation": f"{_score_band_text(foundation_score)}（{foundation_score}分）",
        "knowledge_mastery": f"{_score_band_text(mastery_score)}（{mastery_score}分）",
        "weak_point_distribution": "薄弱点较集中，需要优先补弱" if weak_distribution_score < 55 else ("薄弱点存在但可控" if weak_distribution_score < 75 else "薄弱点分布较稳定"),
        "learning_progress": f"{stage_label}；当前推进度 {progress_score}分",
        "engagement_level": f"{_score_band_text(engagement_score)}（{engagement_score}分）",
        "support_match": f"{_score_band_text(support_match_score)}（{support_match_score}分）",
        "error_pattern_stability": error_pattern or DEFAULT_VALUE,
        "goal_attainment_risk": goal_risk or DEFAULT_VALUE,
        "current_stage_label": stage_label,
        "strong_knowledge_points": strong_summary or DEFAULT_VALUE,
        "weak_knowledge_points": weak_summary or DEFAULT_VALUE,
        "error_pattern": error_pattern,
        "goal_risk": goal_risk,
        "overall_mastery_score": mastery_score,
        "knowledge_mastery_map": knowledge_map,
        "score_details": score_details,
        "dynamic_scores": {
            "knowledge_foundation": foundation_score,
            "knowledge_mastery": mastery_score,
            "weak_point_distribution": weak_distribution_score,
            "learning_progress": progress_score,
            "engagement_level": engagement_score,
            "support_match": support_match_score,
            "error_pattern_stability": error_pattern_score,
            "goal_attainment_risk": goal_risk_score,
        },
    }

def _portrait_dimension_scores(user_id: int, profile: dict) -> dict:
    evidence = _build_portrait_scoring_evidence(user_id, profile)
    dynamic_profile = _derive_learning_profile(profile, evidence)

    if not profile or config.MOCK_AI:
        return _portrait_score_fallback(profile, evidence)

    try:
        prompt = PORTRAIT_SCORE_PROMPT_TEMPLATE.format(
            profile_json=json.dumps({**profile, **dynamic_profile}, ensure_ascii=False, indent=2),
            evidence_json=json.dumps(evidence, ensure_ascii=False, indent=2),
        )
        raw = PlatformLLM().invoke(prompt)
        data = parse_json_with_fallback(raw)
        dimensions_raw = data.get("dimensions") if isinstance(data, dict) else {}

        dimensions = {}
        for key in CORE_PROFILE_DIMENSIONS:
            item = dimensions_raw.get(key) if isinstance(dimensions_raw, dict) else {}
            fallback_score = _safe_int((dynamic_profile.get("dynamic_scores") or {}).get(key), 45)
            fallback_value = _trim_text(dynamic_profile.get(key), 120)
            score = _clamp_score(_safe_int(item.get("score"), fallback_score))
            level = str(item.get("level") or _score_level(score)).strip() or _score_level(score)
            teacher_judgement = str(item.get("teacher_judgement") or fallback_value or "").strip()
            reason = str(item.get("reason") or "").strip()
            if teacher_judgement and reason:
                merged_reason = f"{teacher_judgement}；{reason}"
            else:
                merged_reason = teacher_judgement or reason or f"{DIMENSION_LABELS[key]}当前仍需更多学习证据支撑。"
            if not reason:
                merged_reason = f"{DIMENSION_LABELS[key]}当前已接入学习行为与答题证据，后续会继续随学随新。"
            dimensions[key] = {
                "score": score,
                "level": level,
                "teacher_judgement": teacher_judgement,
                "reason": f"{merged_reason} {(dynamic_profile.get('score_details') or {}).get(key, '')}".strip(),
            }

        if not dimensions:
            return _portrait_score_fallback(profile, evidence)

        filled_core_count = len([key for key in CORE_PROFILE_DIMENSIONS if _normalize_text(dynamic_profile.get(key))])
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
            "dynamic_profile": dynamic_profile,
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
    if not isinstance(scoring, dict) or not scoring.get("dimensions") or scoring.get("scoring_version") != 3:
        return None

    cached_snapshot = _json_loads(latest.get("profile_snapshot"), {})
    current_snapshot = _snapshot_profile_view(profile or {})
    if cached_snapshot == current_snapshot:
        scoring["method"] = scoring.get("method") or "读取最近一次画像评分缓存"
        return scoring
    return None


def _aggregate_profile_payload(user_id: int, profile: dict, refresh_scoring: bool = False) -> dict:
    payload = dict(profile or {})
    evidence = _build_portrait_scoring_evidence(user_id, payload)
    if refresh_scoring:
        payload["portrait_scoring"] = _portrait_dimension_scores(user_id, payload)
    else:
        cached_scoring = _cached_portrait_scoring(user_id, payload)
        payload["portrait_scoring"] = cached_scoring or _portrait_score_fallback(payload, evidence)
    payload["portrait_scoring"]["scoring_version"] = 3
    payload["dynamic_profile"] = (payload.get("portrait_scoring") or {}).get("dynamic_profile") or {}
    payload["learning_events"] = evidence.get("learning_events") or []
    payload["resource_feedback"] = evidence.get("resource_feedback") or []
    payload["resource_usage"] = evidence.get("resource_usage") or []
    payload["learning_effect_overview"] = evidence.get("learning_effect_overview") or {}
    payload["evidence_counts"] = evidence.get("counts") or {}
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
        "weak_knowledge_points": _trim_text(profile.get("weak_knowledge_points"), 160),
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
        # Recover profile fields from persisted dialogue when the asynchronous
        # profile-sync request was interrupted or the user navigated away early.
        session = _active_session(request.user_id, create_if_missing=False)
        recovered_profile = _ensure_session_profile_from_conversation(request.user_id, session) if session else None
        profile = _refresh_aggregate_profile(request.user_id, transient_profile=recovered_profile) if recovered_profile else _cached_aggregate_profile(request.user_id)
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
