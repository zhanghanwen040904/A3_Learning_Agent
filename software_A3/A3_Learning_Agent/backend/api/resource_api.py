import json

from flask import Blueprint, request

from ai.agents import agent_manager
from ai.spark_api import content_audit
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

resource_bp = Blueprint("resource", __name__)


@resource_bp.post("/generate")
@login_required
def generate_resources():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        session = resolve_profile_session(user_id, payload, create_if_missing=True)
        if not session:
            return fail("画像会话不存在", 404)
        session_id = session["id"]
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
        if not profile and not payload.get("dialogue"):
            return fail("未找到学生画像，请先创建画像或传入dialogue", 404)

        dialogue = str(payload.get("dialogue") or payload.get("learning_need") or "")
        if not content_audit(str(dialogue)):
            if dialogue:
                return fail("资源生成输入未通过讯飞内容审核", 403)

        result = agent_manager.run_pipeline(dialogue, stored_profile=profile, request_data=payload)
        batch_id = mysql_db.insert(
            "generation_batch",
            {
                "trace_id": result["trace_id"],
                "user_id": user_id,
                "profile_session_id": session_id,
                "profile_snapshot": json.dumps(result.get("context", {}), ensure_ascii=False),
                "plan": json.dumps(result.get("plan", {}), ensure_ascii=False),
                "status": "completed" if not result.get("errors") else "completed_with_warnings",
                "error_summary": "；".join(result.get("errors", [])),
            },
        )
        saved_resources = []
        for item in result.get("resource_list", []):
            content = str(item.get("content", ""))
            if content and content_audit(content):
                resource_id = mysql_db.insert(
                    "study_resource",
                    {
                        "user_id": user_id,
                        "profile_session_id": session_id,
                        "resource_type": item.get("resource_type", "unknown"),
                        "title": item.get("title", "未命名资源"),
                        "content": content,
                        "batch_id": batch_id,
                        "agent_name": item.get("agent_name"),
                        "knowledge_points": json.dumps(item.get("knowledge_points", []), ensure_ascii=False),
                        "personalization": item.get("personalization"),
                        "quality_score": item.get("quality_score"),
                        "audit_status": "passed" if item.get("quality", {}).get("passed") else "warning",
                        "metadata": json.dumps(
                            {
                                "format": item.get("format"),
                                "quality": item.get("quality"),
                                "retry_count": item.get("retry_count", 0),
                                "duration_ms": item.get("duration_ms", 0),
                                "video_url": item.get("video_url"),
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
                for source in item.get("sources", []):
                    mysql_db.insert(
                        "resource_source",
                        {
                            "resource_id": resource_id,
                            "source_name": source.get("source", "unknown"),
                            "chunk_index": source.get("chunk_index"),
                            "relevance_score": source.get("score"),
                            "retrieval_mode": source.get("retrieval_mode"),
                        },
                    )
                saved_resources.append({"id": resource_id, **item, "content": content})
        score_by_agent = {item.get("agent_name"): item.get("quality_score") for item in result.get("resource_list", [])}
        for event in result.get("trace", []):
            mysql_db.insert(
                "agent_execution",
                {
                    "batch_id": batch_id,
                    "agent_name": event.get("agent"),
                    "status": event.get("status", "unknown"),
                    "message": event.get("message"),
                    "score": score_by_agent.get(event.get("agent")),
                    "retry_count": event.get("retry_count", 0),
                    "duration_ms": event.get("duration_ms", 0),
                },
            )
        mysql_db.execute("UPDATE generation_batch SET finish_time=NOW() WHERE id=%s", (batch_id,))
        result["resource_list"] = saved_resources or result.get("resource_list", [])
        result["batch_id"] = batch_id
        return success(result, "资源生成成功")
    except Exception as exc:
        return fail("资源生成失败", 500, {"error": str(exc)})


@resource_bp.get("/")
@login_required
def list_my_resources():
    try:
        session = resolve_profile_session(request.user_id, create_if_missing=False)
        if not session:
            return success([], "暂无画像会话资源")
        resources = mysql_db.query_all(
            """
            SELECT sr.*
            FROM study_resource sr
            INNER JOIN (
                SELECT resource_type, MAX(id) AS max_id
                FROM study_resource
                WHERE user_id=%s AND profile_session_id=%s
                GROUP BY resource_type
            ) latest ON sr.resource_type = latest.resource_type AND sr.id = latest.max_id
            WHERE sr.user_id=%s AND sr.profile_session_id=%s
            ORDER BY FIELD(sr.resource_type, 'doc', 'quiz', 'reading', 'mindmap', 'code', 'video'), sr.id DESC
            """,
            (request.user_id, session["id"], request.user_id, session["id"]),
        )
        for item in resources:
            for field in ("knowledge_points", "metadata"):
                if isinstance(item.get(field), str):
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            item["sources"] = mysql_db.query_all(
                "SELECT source_name AS source, chunk_index, relevance_score AS score, retrieval_mode FROM resource_source WHERE resource_id=%s",
                (item["id"],),
            )
        return success(resources, "查询成功")
    except Exception as exc:
        return fail("资源查询失败", 500, {"error": str(exc)})


@resource_bp.get("/<int:user_id>")
@login_required
def list_resources(user_id: int):
    return list_my_resources()
