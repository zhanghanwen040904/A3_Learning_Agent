import json
import re

from flask import Blueprint, request

from ai.agents import EvaluatorAgent
from ai.assessment_pipeline import assessment_status, build_assessment_assets, generate_personalized_questions
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

evaluation_bp = Blueprint("evaluation", __name__)
evaluator_agent = EvaluatorAgent()


def _upsert_mastery(user_id: int, knowledge_point: str, score: int, weak_reason: str) -> None:
    mysql_db.upsert_by_unique_key(
        "mastery_record",
        {"user_id": user_id, "knowledge_point": knowledge_point, "mastery_score": score, "weak_reason": weak_reason},
        update_fields=["mastery_score", "weak_reason"],
    )


def _refresh_profile_after_evaluation(user_id: int) -> dict:
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
        update_data["weak_points"] = "、".join(item["knowledge_point"] for item in weak_items[:5])
    if strong_items:
        strong_text = "、".join(item["knowledge_point"] for item in strong_items[:5])
        weak_text = update_data.get("weak_points", "综合应用能力")
        update_data["course_progress"] = f"当前优势知识点：{strong_text}；仍需巩固：{weak_text}"
    elif weak_items:
        update_data["course_progress"] = f"当前薄弱知识点：{update_data['weak_points']}，建议优先复习并完成对应检测题。"

    if update_data:
        mysql_db.update("student_profile", update_data, "user_id=%s", (user_id,))
    return update_data


def _get_profile(user_id: int) -> dict:
    return mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (user_id,)) or {}


def _get_mastery(user_id: int) -> list[dict]:
    return mysql_db.query_all(
        "SELECT * FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC, update_time DESC",
        (user_id,),
    )


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
                "question": str(payload["question"]),
                "answer": str(payload["answer"]),
                "reference_answer": result["reference_answer"],
                "score": result["score"],
                "feedback": result["feedback"],
                "knowledge_point": knowledge_point,
            },
        )

        _upsert_mastery(request.user_id, knowledge_point, int(result["score"]), result["weak_reason"])
        profile_update = _refresh_profile_after_evaluation(request.user_id)
        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
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
        return success({"id": record_id, **result, "profile_update": profile_update}, "练习提交成功")
    except Exception as exc:
        return fail("练习提交失败", 500, {"error": str(exc)})


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
        event_id = mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "event_type": str(payload["event_type"]),
                "knowledge_point": str(payload.get("knowledge_point") or ""),
                "detail": json.dumps(payload.get("detail") or {}, ensure_ascii=False),
            },
        )
        return success({"id": event_id}, "学习行为记录成功")
    except Exception as exc:
        return fail("学习行为记录失败", 500, {"error": str(exc)})
