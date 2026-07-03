from flask import Blueprint, request

from ai.llm_api import audit_content, generate_teaching_video, llm_chat
from config import config
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required

system_bp = Blueprint("system", __name__)


def _mask(value: str) -> str:
    if not value:
        return "未配置"
    if len(value) <= 8:
        return "已配置"
    return f"{value[:4]}****{value[-4:]}"


def _table_count(table_name: str) -> int:
    row = mysql_db.query_one(f"SELECT COUNT(*) AS count FROM `{table_name}`")
    return int(row.get("count") or 0) if row else 0


@system_bp.get("/status")
@login_required
def status():
    try:
        db_status = mysql_db.query_one("SELECT DATABASE() AS database_name, VERSION() AS version") or {}
        tables = [
            {"name": "user", "label": "用户表", "count": _table_count("user"), "usage": "保存注册用户与登录账号"},
            {"name": "student_profile", "label": "学生画像表", "count": _table_count("student_profile"), "usage": "保存学生画像结果"},
            {"name": "study_resource", "label": "学习资源表", "count": _table_count("study_resource"), "usage": "保存文档、题目、图解、代码、视频等资源"},
            {"name": "study_path", "label": "学习路径表", "count": _table_count("study_path"), "usage": "保存个性化学习路径"},
            {"name": "quiz_result", "label": "练习结果表", "count": _table_count("quiz_result"), "usage": "保存答题结果与反馈"},
            {"name": "mastery_record", "label": "掌握度表", "count": _table_count("mastery_record"), "usage": "保存知识点掌握情况"},
            {"name": "learning_event", "label": "学习行为表", "count": _table_count("learning_event"), "usage": "保存问答、练习、资源访问等记录"},
            {"name": "resource_feedback", "label": "资源反馈表", "count": _table_count("resource_feedback"), "usage": "保存学生对资源的评价"},
            {"name": "generation_batch", "label": "生成批次表", "count": _table_count("generation_batch"), "usage": "保存资源生成批次信息"},
            {"name": "agent_execution", "label": "智能体执行表", "count": _table_count("agent_execution"), "usage": "保存智能体执行轨迹"},
            {"name": "resource_source", "label": "资源来源表", "count": _table_count("resource_source"), "usage": "保存资源和知识片段关联"},
        ]

        provider = (config.AI_PROVIDER or "bailian").lower()
        ai_status = {
            "mock_ai": config.MOCK_AI,
            "provider": provider,
            "mode": "mock" if config.MOCK_AI else "live",
            "primary_model": {
                "configured": bool(config.BAILIAN_API_KEY and config.BAILIAN_BASE_URL and config.BAILIAN_MODEL),
                "api_key": _mask(config.BAILIAN_API_KEY),
                "base_url": config.BAILIAN_BASE_URL or "未配置",
                "model": config.BAILIAN_MODEL or "未配置",
            },
            "video": {
                "configured": bool(config.SEEDANCE_API_KEY and config.SEEDANCE_API_URL),
                "api_key": _mask(config.SEEDANCE_API_KEY),
                "url": config.SEEDANCE_API_URL or "未配置",
            },
            "audit_content": {
                "configured": bool(config.CONTENT_AUDIT_API_KEY and config.CONTENT_AUDIT_API_URL),
                "fallback_enabled": not bool(config.CONTENT_AUDIT_API_KEY and config.CONTENT_AUDIT_API_URL),
                "api_key": _mask(config.CONTENT_AUDIT_API_KEY),
                "url": config.CONTENT_AUDIT_API_URL or "未配置，使用本地基础审核兜底",
            },
        }

        return success(
            {
                "database": {
                    "connected": True,
                    "name": db_status.get("database_name"),
                    "version": db_status.get("version"),
                    "host": config.MYSQL_HOST,
                    "port": config.MYSQL_PORT,
                    "user": config.MYSQL_USER,
                    "tables": tables,
                },
                "ai": ai_status,
            },
            "系统状态查询成功",
        )
    except Exception as exc:
        return fail("系统状态查询失败，请检查数据库和 AI 配置", 500, {"error": str(exc)})


@system_bp.post("/test-ai")
@login_required
def test_ai():
    try:
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt") or "请用一句话说明你正在连接 A3 学习助手。")
        llm_result = llm_chat(prompt)
        audit_result = audit_content("人工智能导论课程学习")
        video_result = "未测试"
        if payload.get("test_video"):
            video_result = generate_teaching_video("请生成一个 60 秒以内的课程介绍短视频。")
        return success(
            {
                "mode": "mock" if config.MOCK_AI else "live",
                "provider": config.AI_PROVIDER,
                "mock_ai": config.MOCK_AI,
                "llm_result": llm_result,
                "audit_content_passed": audit_result,
                "video_result": video_result,
            },
            "AI 连通性测试完成",
        )
    except Exception as exc:
        return fail("AI 连通性测试失败", 500, {"error": str(exc)})
