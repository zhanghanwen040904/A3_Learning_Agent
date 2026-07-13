import json
import re
from pathlib import Path

from flask import Blueprint, request

from ai.agents import EvaluatorAgent
from ai.assessment_pipeline import (
    assessment_status,
    build_assessment_assets,
    generate_personalized_questions,
    load_question_bank,
)
from config import config
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

evaluation_bp = Blueprint("evaluation", __name__)
evaluator_agent = EvaluatorAgent()


def _upsert_mastery(user_id: int, knowledge_point: str, score: int, weak_reason: str, profile_session_id=None) -> None:
    mysql_db.upsert_by_unique_key(
        "mastery_record",
        {
            "user_id": user_id,
            "profile_session_id": profile_session_id,
            "knowledge_point": knowledge_point,
            "mastery_score": score,
            "weak_reason": weak_reason,
        },
        update_fields=["profile_session_id", "mastery_score", "weak_reason"],
    )


def _refresh_profile_after_evaluation(user_id: int, profile_session_id=None) -> dict:
    if profile_session_id:
        mastery = mysql_db.query_all(
            "SELECT knowledge_point, mastery_score FROM mastery_record WHERE user_id=%s AND profile_session_id=%s ORDER BY mastery_score ASC",
            (user_id, profile_session_id),
        )
    else:
        mastery = mysql_db.query_all(
            "SELECT knowledge_point, mastery_score FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC",
            (user_id,),
        )
    if not mastery:
        mastery = mysql_db.query_all(
            "SELECT knowledge_point, mastery_score FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC",
            (user_id,),
        )
    if not mastery:
        return {}

    weak_items = [item for item in mastery if int(item.get("mastery_score") or 0) < 70]
    strong_items = [item for item in mastery if int(item.get("mastery_score") or 0) >= 85]
    update_data = {}

    if weak_items:
        weak_text = "、".join(item["knowledge_point"] for item in weak_items[:5])
        update_data["weak_points"] = weak_text
        update_data["weak_knowledge_points"] = weak_text
        update_data["error_prone_points"] = weak_text
    if strong_items:
        strong_text = "、".join(item["knowledge_point"] for item in strong_items[:5])
        weak_text = update_data.get("weak_points", "综合应用能力")
        update_data["course_progress"] = f"当前优势知识点：{strong_text}；仍需巩固：{weak_text}"
        update_data["recent_progress"] = f"已形成优势知识点：{strong_text}"
    elif weak_items:
        update_data["course_progress"] = f"当前薄弱知识点：{update_data['weak_points']}，建议优先复习并完成对应检测题。"
        update_data["recent_progress"] = "正在围绕薄弱知识点进行针对性纠错和巩固。"

    avg_mastery = sum(int(item.get("mastery_score") or 0) for item in mastery) / max(len(mastery), 1)
    if avg_mastery >= 85:
        update_data["mastery_level"] = "掌握较好"
    elif avg_mastery >= 70:
        update_data["mastery_level"] = "有一定基础"
    elif avg_mastery >= 55:
        update_data["mastery_level"] = "基础未稳"
    else:
        update_data["mastery_level"] = "入门起步"
    update_data["engagement_level"] = "持续练习中"

    if update_data:
        if profile_session_id:
            mysql_db.update("student_profile", update_data, "user_id=%s AND profile_session_id=%s", (user_id, profile_session_id))
        else:
            mysql_db.update("student_profile", update_data, "user_id=%s", (user_id,))
    return update_data


def _refresh_portrait_after_evaluation(user_id: int, profile_session_id, trigger_source: str) -> dict:
    if not profile_session_id:
        return {}
    from api.profile_api import _aggregate_profile_payload, _persist_portrait_snapshot, _refresh_aggregate_profile

    aggregate_profile = _aggregate_profile_payload(
        user_id,
        _refresh_aggregate_profile(user_id),
        refresh_scoring=True,
    )
    _persist_portrait_snapshot(
        user_id=user_id,
        profile_session_id=profile_session_id,
        profile=aggregate_profile,
        portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
        trigger_source=trigger_source,
        force=True,
    )
    return aggregate_profile


def _get_profile(user_id: int) -> dict:
    return mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (user_id,)) or {}


def _get_mastery(user_id: int) -> list[dict]:
    return mysql_db.query_all(
        "SELECT * FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC, update_time DESC",
        (user_id,),
    )


def _chapter_from_knowledge_path(knowledge_path: str, knowledge_point: str = "") -> str:
    text = str(knowledge_path or knowledge_point or "").strip()
    parts = [part.strip() for part in re.split(r"[/＞>\\|]", text) if part.strip()]
    return parts[0] if parts else (str(knowledge_point or "未分类").strip() or "未分类")


def _json_value(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback



def _safe_bigint(value):
    try:
        return int(value) if str(value or "").isdigit() else None
    except Exception:
        return None


def _list_assessment_knowledge_points() -> list[dict]:
    question_bank = load_question_bank()

    def _is_valid_knowledge_option(text: str) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        if len(value) <= 1:
            return False
        if "/" in value or "\\" in value:
            return False
        if "习 题" in value or "试 卷" in value or "附 录" in value or "第" in value and "章" in value:
            return False
        if value.startswith("(") or value.startswith("（") or value.startswith("."):
            return False
        if re.fullmatch(r"[A-Z][A-Z0-9_\- ]*", value):
            return False
        if any(token in value for token in ["？", "?", "。", "，", ",", "：", ":", "例如", "请", "说明", "设计", "为什么"]):
            return False
        if any(value.startswith(prefix) for prefix in ["的", "和", "在", "将", "把", "按", "从", "对", "使", "用", "若", "当", "按"]):
            return False
        if any(value.endswith(suffix) for suffix in ["的", "了", "吗", "呢", "（", "(", "）", ")"]):
            return False
        normalized = re.sub(r"\s+", "", value)
        if len(normalized) <= 2 and normalized not in {"测试", "继承", "对象", "模型"}:
            return False
        if normalized.startswith(("的", "和", "在")) or normalized.endswith(("的", "了")):
            return False
        noisy_exact = {
            "事实上",
            "出现这种",
            "所谓自然执行",
            "但是",
            "复杂",
            "科学",
            "开发",
            "模型",
            "程序",
            "软件",
            "描述",
            "在",
            "当",
            "非",
            "不同",
            "关系",
            "开始",
            "有效",
            "每个",
            "这些",
            "对象",
            "和过程",
            "和数据",
            "化的",
            "的过程",
            "的任务",
            "性需求",
            "的信息",
            "的信息域",
            "用面向对象",
            "类中定义",
            "调试（也",
            "选择数据（",
            "有两种",
            "减少风险",
            "互相补充",
            "各有所长",
            "发送分支",
            "实例(instance)",
            "references",
            "REFERENCES",
        }
        if value in noisy_exact:
            return False
        return True

    def _normalize_for_match(text: str) -> str:
        cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", str(text or "").strip())
        cleaned = cleaned.replace("（", "(").replace("）", ")")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", cleaned)
        return cleaned.lower()

    def _clean_section_title(text: str) -> str:
        cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", str(text or "").strip())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_valid_tree_path(parts: list[str]) -> bool:
        if not parts:
            return False
        path_text = "/".join(parts)
        blocked_tokens = ["习题", "习 题", "试卷", "试 卷", "附录", "附 录", "注意", "REFERENCES"]
        return not any(token in path_text for token in blocked_tokens)

    def _display_label(text: str) -> str:
        value = str(text or "").strip()
        replacements = [
            (r"^识别(.+)$", r"\1"),
            (r"^调整(.+)$", r"\1"),
            (r"^建立(.+)$", r"\1"),
            (r"^确定(.+)$", r"\1"),
            (r"^设计(.+)$", r"\1"),
            (r"^画出?(.+)$", r"\1"),
            (r"^描述(.+)$", r"\1"),
            (r"^选择(.+)$", r"\1"),
            (r"^提高(.+)$", r"\1"),
            (r"^实现(.+)$", r"\1"),
        ]
        for pattern, repl in replacements:
            candidate = re.sub(pattern, repl, value)
            if candidate != value and _is_valid_knowledge_option(candidate):
                return candidate
        return value

    def _sort_key_from_section_path(parts: list[str]) -> tuple:
        def _part_key(part: str) -> tuple:
            text = str(part or "").strip()
            match = re.match(r"^(\d+(?:\.\d+)*)", text)
            if not match:
                return (1, text)
            numbers = tuple(int(item) for item in match.group(1).split("."))
            return (0, numbers, text)

        return tuple(_part_key(part) for part in parts)

    canonical_nodes = []
    textbook_points_dir = Path(config.RAG_SOURCE_DIR).parent / "knowledge_points_json"
    for path in sorted(textbook_points_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("knowledge_points") or []:
            if not item.get("student_visible", True):
                continue
            section_path = [str(part or "").strip() for part in (item.get("section_path") or []) if str(part or "").strip()]
            if not _is_valid_tree_path(section_path):
                continue
            title = str(item.get("title") or item.get("normalized_title") or "").strip()
            if not _is_valid_knowledge_option(title):
                continue
            if len(section_path) < 2:
                continue
            aliases = {title, str(item.get("normalized_title") or "").strip()}
            aliases.update(_clean_section_title(part) for part in section_path)
            aliases = {alias for alias in aliases if _is_valid_knowledge_option(alias)}
            canonical_nodes.append(
                {
                    "value": title,
                    "label": _display_label(title),
                    "chapter": _clean_section_title(section_path[1]),
                    "path": " / ".join(_clean_section_title(part) for part in section_path),
                    "aliases": aliases,
                    "chapter_order": _sort_key_from_section_path(section_path[:2]),
                    "option_order": _sort_key_from_section_path(section_path),
                }
            )

    canonical_map: dict[str, dict] = {}
    for node in canonical_nodes:
        if node["value"] not in canonical_map:
            canonical_map[node["value"]] = node

    raw_counter: dict[str, int] = {}

    def _register_raw(value: str) -> None:
        key = str(value or "").strip()
        if not _is_valid_knowledge_option(key):
            return
        raw_counter[key] = raw_counter.get(key, 0) + 1

    for item in question_bank:
        primary_titles = item.get("primary_knowledge_titles") or []
        related_titles = item.get("related_knowledge_titles") or []
        for candidate in primary_titles:
            _register_raw(candidate)
        for candidate in related_titles:
            _register_raw(candidate)
        _register_raw(item.get("knowledge_point"))

    alias_to_canonical: dict[str, str] = {}
    for node in canonical_map.values():
        for alias in node["aliases"]:
            alias_to_canonical[_normalize_for_match(alias)] = node["value"]

    manual_aliases = {
        "继承": "识别继承关系",
        "类继承": "识别继承关系",
        "继承重用": "识别继承关系",
        "多态重用": "多态性",
        "测试": "软件测试基础",
        "面向对象方法学概述": "面向对象方法学引论",
    }

    counts_by_canonical: dict[str, int] = {value: 0 for value in canonical_map}

    def _resolve_canonical(raw_label: str) -> str | None:
        normalized_raw = _normalize_for_match(raw_label)
        if not normalized_raw:
            return None
        manual_target = manual_aliases.get(str(raw_label or "").strip())
        if manual_target and manual_target in canonical_map:
            return manual_target
        direct = alias_to_canonical.get(normalized_raw)
        if direct:
            return direct
        best_value = None
        best_score = 0
        for node in canonical_map.values():
            for alias in node["aliases"]:
                normalized_alias = _normalize_for_match(alias)
                if not normalized_alias:
                    continue
                score = 0
                if normalized_raw == normalized_alias:
                    score = 100
                elif normalized_raw in normalized_alias or normalized_alias in normalized_raw:
                    min_length = min(len(normalized_raw), len(normalized_alias))
                    if min_length >= 2:
                        score = 70 + min_length
                if score > best_score:
                    best_score = score
                    best_value = node["value"]
        return best_value if best_score >= 73 else None

    for raw_label, count in raw_counter.items():
        canonical_value = _resolve_canonical(raw_label)
        if canonical_value:
            counts_by_canonical[canonical_value] += count

    items = []
    groups_map: dict[str, list[dict]] = {}
    for value, node in canonical_map.items():
        count = int(counts_by_canonical.get(value) or 0)
        if count <= 0:
            continue
        item = {
            "value": value,
            "label": node["label"],
            "chapter": node["chapter"],
            "path": node["path"],
            "type": "knowledge_point",
            "question_count": count,
            "chapter_order": node["chapter_order"],
            "option_order": node["option_order"],
        }
        items.append(item)
        groups_map.setdefault(node["chapter"], []).append(item)

    items.sort(key=lambda item: (item["chapter_order"], item["option_order"], item["label"]))
    groups = []
    for chapter, options in groups_map.items():
        options.sort(key=lambda item: (item["option_order"], item["label"]))
        groups.append(
            {
                "label": chapter,
                "options": options,
                "all_values": [item["value"] for item in options],
                "knowledge_count": len(options),
                "chapter_order": options[0]["chapter_order"] if options else ((9, chapter),),
            }
        )
    groups.sort(key=lambda group: group["chapter_order"])
    return {"items": items, "groups": groups}

def _wrong_book_payload(user_id: int, payload: dict, result: dict | None = None, quiz_result_id=None) -> dict:
    question = str(payload.get("question") or payload.get("prompt") or "")
    knowledge_path = str(payload.get("knowledge_path") or payload.get("knowledge_point") or "")
    knowledge_point = str(payload.get("knowledge_point") or knowledge_path or "未分类")
    result = result or payload.get("result") or {}
    return {
        "user_id": user_id,
        "quiz_result_id": _safe_bigint(quiz_result_id or payload.get("quiz_result_id") or payload.get("id")),
        "question": question,
        "question_type": str(payload.get("question_type") or ""),
        "options_json": json.dumps(payload.get("options") or [], ensure_ascii=False),
        "answer": str(payload.get("answer") or payload.get("userAnswer") or ""),
        "reference_answer": str(payload.get("reference_answer") or result.get("reference_answer") or ""),
        "explanation": str(payload.get("explanation") or result.get("explanation") or ""),
        "common_mistake": str(payload.get("common_mistake") or result.get("common_mistake") or ""),
        "scoring_points": json.dumps(payload.get("scoring_points") or result.get("scoring_points") or [], ensure_ascii=False),
        "knowledge_point": knowledge_point,
        "knowledge_path": knowledge_path,
        "chapter": str(payload.get("chapter") or _chapter_from_knowledge_path(knowledge_path, knowledge_point)),
        "difficulty": str(payload.get("difficulty") or ""),
        "score": int(result.get("score") or payload.get("score") or 0),
        "feedback": str(result.get("feedback") or payload.get("feedback") or ""),
        "last_result": json.dumps(result or {}, ensure_ascii=False),
    }


@evaluation_bp.post("/rebuild-bank")
@login_required
def rebuild_bank():
    try:
        payload = request.get_json(silent=True) or {}
        result = build_assessment_assets(force=bool(payload.get("force", True)))
        return success(result, "知识点与题库已重建")
    except Exception as exc:
        return fail("题库重建失败", 500, {"error": str(exc)})


@evaluation_bp.get("/bank-status")
@login_required
def bank_status():
    try:
        return success(assessment_status(), "题库状态查询成功")
    except Exception as exc:
        return fail("题库状态查询失败", 500, {"error": str(exc)})


@evaluation_bp.get("/knowledge-points")
@login_required
def knowledge_points():
    try:
        return success(
            _list_assessment_knowledge_points(),
            "评估知识点列表查询成功",
        )
    except Exception as exc:
        return fail("评估知识点列表查询失败", 500, {"error": str(exc)})


@evaluation_bp.post("/questions")
@login_required
def generate_questions():
    try:
        payload = request.get_json(silent=True) or {}
        profile = _get_profile(request.user_id)
        mastery = _get_mastery(request.user_id)
        count = int(payload.get("count") or 5)
        knowledge_point = str(payload.get("knowledge_point") or "")
        knowledge_points = payload.get("knowledge_points") or []
        if isinstance(knowledge_points, str):
            knowledge_points = [item.strip() for item in re.split(r"[、，,；;]", knowledge_points) if item.strip()]
        stage_index = payload.get("stage_index")
        try:
            stage_index = int(stage_index) if stage_index is not None and stage_index != "" else None
        except Exception:
            stage_index = None
        stage_title = str(payload.get("stage_title") or "")
        result = generate_personalized_questions(
            profile,
            mastery,
            count=count,
            knowledge_point=knowledge_point,
            knowledge_points=knowledge_points,
            stage_index=stage_index,
            stage_title=stage_title,
        )
        result["profile_snapshot"] = {
            "weak_points": profile.get("weak_points", ""),
            "study_goal": profile.get("study_goal", ""),
            "course_progress": profile.get("course_progress", ""),
        }
        return success(result, "个性化检测题生成成功")
    except Exception as exc:
        return fail("个性化检测题生成失败", 500, {"error": str(exc)})


@evaluation_bp.post("/submit")
@login_required
def submit_quiz():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question", "answer"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        session_id = session["id"] if session else None

        knowledge_point = str(payload.get("knowledge_point") or "机器学习基础")
        reference_answer = str(payload.get("reference_answer") or "")
        result = evaluator_agent.grade(
            str(payload["question"]),
            str(payload["answer"]),
            reference_answer,
            knowledge_point,
            str(payload.get("explanation") or ""),
            str(payload.get("common_mistake") or ""),
            payload.get("scoring_points") or [],
            str(payload.get("question_type") or ""),
            str(payload.get("feedback_correct") or ""),
            str(payload.get("feedback_wrong") or ""),
        )
        record_id = mysql_db.insert(
            "quiz_result",
            {
                "user_id": request.user_id,
                "profile_session_id": session_id,
                "question": str(payload["question"]),
                "answer": str(payload["answer"]),
                "reference_answer": result["reference_answer"],
                "score": result["score"],
                "feedback": result["feedback"],
                "knowledge_point": knowledge_point,
            },
        )

        _upsert_mastery(request.user_id, knowledge_point, int(result["score"]), result["weak_reason"], profile_session_id=session_id)
        profile_update = _refresh_profile_after_evaluation(request.user_id, profile_session_id=session_id)
        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "profile_session_id": session_id,
                "event_type": "finish_quiz",
                "knowledge_point": knowledge_point,
                "detail": json.dumps(
                    {
                        "score": result["score"],
                        "question": payload["question"],
                        "is_correct": result["is_correct"],
                        "missed_keywords": result["missed_keywords"],
                    },
                    ensure_ascii=False,
                ),
            },
        )
        aggregate_profile = _refresh_portrait_after_evaluation(request.user_id, session_id, "evaluation_submit")
        return success({"id": record_id, **result, "profile_update": profile_update, "aggregate_profile": aggregate_profile, "profile_session_id": session_id}, "练习提交成功")
    except Exception as exc:
        return fail("练习提交失败", 500, {"error": str(exc)})



@evaluation_bp.post("/wrong-book")
@login_required
def add_wrong_book_item():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)
        data = _wrong_book_payload(request.user_id, payload, payload.get("result") or {})
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        if session:
            data["profile_session_id"] = session["id"]
        existing = mysql_db.query_one(
            "SELECT id FROM quiz_wrong_book WHERE user_id=%s AND question=%s AND knowledge_point=%s ORDER BY id DESC LIMIT 1",
            (request.user_id, data["question"], data["knowledge_point"]),
        )
        if existing:
            mysql_db.update(
                "quiz_wrong_book",
                {key: value for key, value in data.items() if key != "user_id"},
                "id=%s AND user_id=%s",
                (existing["id"], request.user_id),
            )
            item_id = existing["id"]
        else:
            item_id = mysql_db.insert("quiz_wrong_book", data)
        return success({"id": item_id}, "已加入错题本")
    except Exception as exc:
        return fail("加入错题本失败", 500, {"error": str(exc)})


@evaluation_bp.get("/wrong-book")
@login_required
def list_wrong_book():
    try:
        rows = mysql_db.query_all(
            "SELECT * FROM quiz_wrong_book WHERE user_id=%s ORDER BY chapter ASC, knowledge_point ASC, update_time DESC",
            (request.user_id,),
        )
        groups = {}
        items = []
        for row in rows:
            row["options"] = _json_value(row.pop("options_json", None), [])
            row["scoring_points"] = _json_value(row.get("scoring_points"), [])
            row["last_result"] = _json_value(row.get("last_result"), {})
            row["create_time"] = str(row.get("create_time") or "")
            row["update_time"] = str(row.get("update_time") or "")
            chapter = row.get("chapter") or "未分类"
            point = row.get("knowledge_point") or "未分类"
            groups.setdefault(chapter, {}).setdefault(point, []).append(row)
            items.append(row)
        tree = [
            {
                "chapter": chapter,
                "count": sum(len(v) for v in point_map.values()),
                "points": [
                    {"knowledge_point": point, "count": len(point_items), "items": point_items}
                    for point, point_items in point_map.items()
                ],
            }
            for chapter, point_map in groups.items()
        ]
        return success({"tree": tree, "items": items}, "错题本读取成功")
    except Exception as exc:
        return fail("错题本读取失败", 500, {"error": str(exc)})


@evaluation_bp.post("/wrong-book/<int:item_id>/submit")
@login_required
def submit_wrong_book_item(item_id: int):
    try:
        payload = request.get_json(silent=True) or {}
        answer = str(payload.get("answer") or "").strip()
        if not answer:
            return fail("请先填写答案", 400)
        item = mysql_db.query_one("SELECT * FROM quiz_wrong_book WHERE id=%s AND user_id=%s", (item_id, request.user_id))
        if not item:
            return fail("错题不存在", 404)
        result = evaluator_agent.grade(
            str(item.get("question") or ""),
            answer,
            str(item.get("reference_answer") or ""),
            str(item.get("knowledge_point") or ""),
            str(item.get("explanation") or ""),
            str(item.get("common_mistake") or ""),
            _json_value(item.get("scoring_points"), []),
            str(item.get("question_type") or ""),
        )
        mysql_db.update(
            "quiz_wrong_book",
            {
                "answer": answer,
                "score": int(result.get("score") or 0),
                "feedback": str(result.get("feedback") or ""),
                "explanation": str(result.get("explanation") or item.get("explanation") or ""),
                "common_mistake": str(result.get("common_mistake") or item.get("common_mistake") or ""),
                "last_result": json.dumps(result, ensure_ascii=False),
                "review_count": int(item.get("review_count") or 0) + 1,
            },
            "id=%s AND user_id=%s",
            (item_id, request.user_id),
        )
        session_id = item.get("profile_session_id")
        _upsert_mastery(request.user_id, str(item.get("knowledge_point") or ""), int(result["score"]), result["weak_reason"], profile_session_id=session_id)
        profile_update = _refresh_profile_after_evaluation(request.user_id, profile_session_id=session_id)
        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "profile_session_id": session_id,
                "event_type": "retry_wrong_book",
                "knowledge_point": str(item.get("knowledge_point") or ""),
                "detail": json.dumps(
                    {
                        "wrong_book_id": item_id,
                        "score": result.get("score"),
                        "is_correct": result.get("is_correct"),
                    },
                    ensure_ascii=False,
                ),
            },
        )
        aggregate_profile = _refresh_portrait_after_evaluation(request.user_id, session_id, "wrong_book_retry")
        return success({**result, "profile_update": profile_update, "aggregate_profile": aggregate_profile, "profile_session_id": session_id}, "错题复做判题完成")
    except Exception as exc:
        return fail("错题复做失败", 500, {"error": str(exc)})


@evaluation_bp.delete("/wrong-book/<int:item_id>")
@login_required
def delete_wrong_book_item(item_id: int):
    try:
        mysql_db.delete("quiz_wrong_book", "id=%s AND user_id=%s", (item_id, request.user_id))
        return success({}, "错题已移除")
    except Exception as exc:
        return fail("错题移除失败", 500, {"error": str(exc)})


@evaluation_bp.get("/summary")
@login_required
def summary():
    try:
        quiz_results = mysql_db.query_all(
            "SELECT * FROM quiz_result WHERE user_id=%s ORDER BY create_time DESC LIMIT 20",
            (request.user_id,),
        )
        mastery = _get_mastery(request.user_id)
        events = mysql_db.query_all(
            "SELECT * FROM learning_event WHERE user_id=%s ORDER BY create_time DESC LIMIT 20",
            (request.user_id,),
        )
        avg_score = round(sum(int(item.get("score") or 0) for item in quiz_results) / len(quiz_results), 1) if quiz_results else 0
        weak_points = [item for item in mastery if int(item.get("mastery_score") or 0) < 70]
        if weak_points:
            next_tasks = [f"优先复习 {item['knowledge_point']}，并完成对应练习题与解析回顾。" for item in weak_points[:3]]
        else:
            next_tasks = [
                "继续完成综合应用题，巩固知识迁移能力。",
                "结合资源区的代码案例完成一次实操。",
                "挑选尚未覆盖的知识点继续检测，完善掌握图谱。",
            ]
        return success(
            {
                "avg_score": avg_score,
                "quiz_count": len(quiz_results),
                "mastery": mastery,
                "weak_points": weak_points,
                "quiz_results": quiz_results,
                "events": events,
                "next_tasks": next_tasks,
                "profile": _get_profile(request.user_id),
                "bank_status": assessment_status(),
            },
            "学习评估查询成功",
        )
    except Exception as exc:
        return fail("学习评估查询失败", 500, {"error": str(exc)})


@evaluation_bp.post("/event")
@login_required
def record_event():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["event_type"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        event_id = mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "profile_session_id": session["id"] if session else None,
                "event_type": str(payload["event_type"]),
                "knowledge_point": str(payload.get("knowledge_point") or ""),
                "detail": json.dumps(payload.get("detail") or {}, ensure_ascii=False),
            },
        )
        return success({"id": event_id}, "学习行为记录成功")
    except Exception as exc:
        return fail("学习行为记录失败", 500, {"error": str(exc)})
