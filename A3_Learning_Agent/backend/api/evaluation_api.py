import json
import re

from flask import Blueprint, request

from ai.agents import EvaluatorAgent
from ai.assessment_pipeline import assessment_status, build_assessment_assets, generate_personalized_questions
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
