from flask import Blueprint, request

from ai.agents import agent_manager
from ai.spark_api import content_audit
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required

resource_bp = Blueprint("resource", __name__)


@resource_bp.post("/generate")
@login_required
def generate_resources():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (user_id,))
        if not profile and not payload.get("dialogue"):
            return fail("未找到学生画像，请先创建画像或传入dialogue", 404)

        dialogue = payload.get("dialogue") or f"请基于该学生画像生成学习资源：{profile}"
        if not content_audit(str(dialogue)):
            return fail("资源生成输入未通过讯飞内容审核", 403)

        result = agent_manager.run_pipeline(str(dialogue))
        saved_resources = []
        for item in result.get("resource_list", []):
            content = str(item.get("content", ""))
            if content and content_audit(content):
                resource_id = mysql_db.insert(
                    "study_resource",
                    {
                        "user_id": user_id,
                        "resource_type": item.get("resource_type", "unknown"),
                        "title": item.get("title", "未命名资源"),
                        "content": content,
                    },
                )
                saved_resources.append({"id": resource_id, **item, "content": content})
        result["resource_list"] = saved_resources or result.get("resource_list", [])
        return success(result, "资源生成成功")
    except Exception as exc:
        return fail("资源生成失败", 500, {"error": str(exc)})


@resource_bp.get("/")
@login_required
def list_my_resources():
    try:
        resources = mysql_db.query_all(
            """
            SELECT sr.*
            FROM study_resource sr
            INNER JOIN (
                SELECT resource_type, MAX(id) AS max_id
                FROM study_resource
                WHERE user_id=%s
                GROUP BY resource_type
            ) latest ON sr.resource_type = latest.resource_type AND sr.id = latest.max_id
            WHERE sr.user_id=%s
            ORDER BY FIELD(sr.resource_type, 'doc', 'quiz', 'reading', 'mindmap', 'code', 'video'), sr.id DESC
            """,
            (request.user_id, request.user_id),
        )
        return success(resources, "查询成功")
    except Exception as exc:
        return fail("资源查询失败", 500, {"error": str(exc)})


@resource_bp.get("/<int:user_id>")
@login_required
def list_resources(user_id: int):
    return list_my_resources()
