import json

from flask import Blueprint, request

from ai.rag import retrieve_knowledge
from ai.spark_api import content_audit, spark_chat
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required

path_bp = Blueprint("path", __name__)


@path_bp.post("/generate")
@login_required
def generate_learning_path():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        profile = payload.get("profile") or mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (user_id,))
        if not profile:
            return fail("未找到学生画像，无法生成学习路径", 404)

        profile_text = json.dumps(profile, ensure_ascii=False, default=str)
        if not content_audit(profile_text):
            return fail("画像内容未通过讯飞内容审核", 403)

        knowledge = retrieve_knowledge(str(profile.get("weak_points") or profile.get("study_goal") or "人工智能导论"), top_k=3)
        prompt = f"""
你是人工智能导论课程学习规划师。请基于学生画像和教材原文，生成个性化阶梯式学习路径。
要求：
1. 只基于教材原文和画像，不编造课程知识；
2. 明确学习顺序、每一步目标、推荐资源类型、练习方式和评估指标；
3. 返回Markdown格式，适合前端直接渲染。
学生画像：{profile_text}
教材原文：
{knowledge}
""".strip()
        path_content = spark_chat(prompt)
        if not content_audit(path_content):
            return fail("生成的学习路径未通过讯飞内容审核", 403)

        path_id = mysql_db.insert("study_path", {"user_id": user_id, "path_content": path_content, "status": "active"})
        return success({"id": path_id, "user_id": user_id, "path_content": path_content, "status": "active"}, "学习路径生成成功")
    except Exception as exc:
        return fail("学习路径生成失败", 500, {"error": str(exc)})


@path_bp.get("/")
@login_required
def list_my_paths():
    try:
        paths = mysql_db.query_all("SELECT * FROM study_path WHERE user_id=%s ORDER BY create_time DESC", (request.user_id,))
        return success(paths, "查询成功")
    except Exception as exc:
        return fail("学习路径查询失败", 500, {"error": str(exc)})


@path_bp.get("/<int:user_id>")
@login_required
def list_paths(user_id: int):
    return list_my_paths()
