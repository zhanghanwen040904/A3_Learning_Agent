import json

from flask import Blueprint, request

from ai.agents import EvaluatorAgent
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
    mastery = mysql_db.query_all("SELECT knowledge_point, mastery_score FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC", (user_id,))
    if not mastery:
        return {}
    weak_items = [item for item in mastery if int(item.get("mastery_score") or 0) < 70]
    strong_items = [item for item in mastery if int(item.get("mastery_score") or 0) >= 85]
    update_data = {}
    if weak_items:
        update_data["weak_points"] = "、".join(item["knowledge_point"] for item in weak_items[:5])
    if strong_items:
        update_data["course_progress"] = f"已较好掌握：{'、'.join(item['knowledge_point'] for item in strong_items[:5])}；需继续巩固：{update_data.get('weak_points', '综合应用能力')}"
    elif weak_items:
        update_data["course_progress"] = f"当前薄弱知识点：{update_data['weak_points']}，建议优先复习并完成基础练习。"
    if update_data:
        mysql_db.update("student_profile", update_data, "user_id=%s", (user_id,))
    return update_data


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
        result = evaluator_agent.grade(str(payload["question"]), str(payload["answer"]), reference_answer, knowledge_point)
        record_id = mysql_db.insert(
            "quiz_result",
            {
                "user_id": request.user_id,
                "question": str(payload["question"]),
                "answer": str(payload["answer"]),
                "reference_answer": reference_answer,
                "score": result["score"],
                "feedback": result["feedback"],
                "knowledge_point": knowledge_point,
            },
        )
        _upsert_mastery(request.user_id, knowledge_point, int(result["score"]), result["feedback"])
        profile_update = _refresh_profile_after_evaluation(request.user_id)
        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "event_type": "finish_quiz",
                "knowledge_point": knowledge_point,
                "detail": json.dumps({"score": result["score"], "question": payload["question"]}, ensure_ascii=False),
            },
        )
        return success({"id": record_id, **result, "profile_update": profile_update}, "练习提交成功")
    except Exception as exc:
        return fail("练习提交失败", 500, {"error": str(exc)})


@evaluation_bp.get("/summary")
@login_required
def summary():
    try:
        quiz_results = mysql_db.query_all("SELECT * FROM quiz_result WHERE user_id=%s ORDER BY create_time DESC LIMIT 20", (request.user_id,))
        mastery = mysql_db.query_all("SELECT * FROM mastery_record WHERE user_id=%s ORDER BY mastery_score ASC", (request.user_id,))
        events = mysql_db.query_all("SELECT * FROM learning_event WHERE user_id=%s ORDER BY create_time DESC LIMIT 20", (request.user_id,))
        avg_score = 0
        if quiz_results:
            avg_score = round(sum(int(item.get("score") or 0) for item in quiz_results) / len(quiz_results), 1)
        weak_points = [item for item in mastery if int(item.get("mastery_score") or 0) < 70]
        next_tasks = []
        if weak_points:
            next_tasks = [f"复习 {item['knowledge_point']}，完成基础概念题并查看相关课程讲解文档" for item in weak_points[:3]]
        else:
            next_tasks = ["完成监督学习与无监督学习综合练习", "阅读神经网络与深度学习章节", "尝试运行代码实操案例"]
        return success(
            {
                "avg_score": avg_score,
                "quiz_count": len(quiz_results),
                "mastery": mastery,
                "weak_points": weak_points,
                "quiz_results": quiz_results,
                "events": events,
                "next_tasks": next_tasks,
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
