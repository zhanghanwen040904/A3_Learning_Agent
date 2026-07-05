import json

from flask import Blueprint, request

from ai.agents import SafetyAgent
from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.spark_api import content_audit, spark_chat
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required

path_bp = Blueprint("path", __name__)
safety_agent = SafetyAgent()


def _session_id_from_request(payload: dict | None = None):
    payload = payload or {}
    raw = payload.get("profile_session_id") or request.args.get("profile_session_id")
    if raw in (None, "", "null", "undefined"):
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _active_session_id(user_id: int, payload: dict | None = None):
    session_id = _session_id_from_request(payload)
    if session_id:
        row = mysql_db.query_one("SELECT id FROM profile_session WHERE id=%s AND user_id=%s", (session_id, user_id))
        return row["id"] if row else None
    row = mysql_db.query_one(
        "SELECT id FROM profile_session WHERE user_id=%s AND is_active=1 ORDER BY update_time DESC LIMIT 1",
        (user_id,),
    )
    if row:
        return row["id"]
    row = mysql_db.query_one("SELECT id FROM profile_session WHERE user_id=%s ORDER BY update_time DESC LIMIT 1", (user_id,))
    return row["id"] if row else None


@path_bp.post("/generate")
@login_required
def generate_learning_path():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        session_id = _active_session_id(user_id, payload)
        if not session_id:
            return fail("请先新建画像对话并生成画像", 404)

        profile = payload.get("profile") or mysql_db.query_one(
            "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (user_id, session_id),
        )
        if not profile:
            return fail("当前画像为空，无法生成学习路径", 404)

        profile_text = json.dumps(profile, ensure_ascii=False, default=str)
        if not content_audit(profile_text):
            return fail("画像内容未通过内容审核", 403)

        query = str(profile.get("weak_points") or profile.get("study_goal") or profile.get("target_course") or "软件工程")
        knowledge = retrieve_knowledge(query, top_k=3)
        sources = retrieve_knowledge_items(query, top_k=3)
        prompt = f"""
你是软件工程课程学习规划师。请基于学生画像和教材原文，生成个性化阶段式学习路径。

要求：
1. 只基于教材原文和学生画像，不编造课程知识。
2. 明确学习顺序、每一步目标、推荐资源类型、练习方式和评估指标。
3. 输出 Markdown，语言简洁清楚，适合前端直接渲染。
4. 最后加入“参考依据”小节，列出教材来源。

学生画像：
{profile_text}

教材原文：
{knowledge}
""".strip()
        path_content = spark_chat(prompt)
        if not content_audit(path_content):
            return fail("生成的学习路径未通过内容审核", 403)

        safety = safety_agent.review(path_content, sources)
        path_id = mysql_db.insert(
            "study_path",
            {
                "user_id": user_id,
                "profile_session_id": session_id,
                "path_content": path_content,
                "status": "active",
            },
        )
        return success(
            {
                "id": path_id,
                "user_id": user_id,
                "profile_session_id": session_id,
                "path_content": path_content,
                "status": "active",
                "sources": sources,
                "safety": safety,
            },
            "学习路径生成成功",
        )
    except Exception as exc:
        return fail("学习路径生成失败", 500, {"error": str(exc)})


@path_bp.get("/")
@login_required
def list_my_paths():
    try:
        session_id = _active_session_id(request.user_id)
        if not session_id:
            return success([], "当前没有画像会话")

        profile = mysql_db.query_one(
            "SELECT id FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session_id),
        )
        if not profile:
            return success([], "当前画像为空，暂无学习路径")

        paths = mysql_db.query_all(
            "SELECT * FROM study_path WHERE user_id=%s AND profile_session_id=%s ORDER BY create_time DESC",
            (request.user_id, session_id),
        )
        return success(paths, "查询成功")
    except Exception as exc:
        return fail("学习路径查询失败", 500, {"error": str(exc)})


@path_bp.get("/<int:user_id>")
@login_required
def list_paths(user_id: int):
    return list_my_paths()
