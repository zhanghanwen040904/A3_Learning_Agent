from flask import Blueprint, request

from ai.spark_api import content_audit, see_dance_generate, spark_chat
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
            {"name": "user", "label": "用户登录表", "count": _table_count("user"), "usage": "保存注册用户和登录账号"},
            {"name": "student_profile", "label": "学生画像表", "count": _table_count("student_profile"), "usage": "保存六维动态学习画像"},
            {"name": "study_resource", "label": "学习资源表", "count": _table_count("study_resource"), "usage": "保存多智能体生成的文档、题库、思维导图、代码和视频任务"},
            {"name": "study_path", "label": "学习路径表", "count": _table_count("study_path"), "usage": "保存个性化学习路径"},
            {"name": "quiz_result", "label": "练习结果表", "count": _table_count("quiz_result"), "usage": "保存练习答案、得分和反馈"},
            {"name": "mastery_record", "label": "掌握度表", "count": _table_count("mastery_record"), "usage": "保存知识点掌握度，用于更新画像和路径"},
            {"name": "learning_event", "label": "学习行为表", "count": _table_count("learning_event"), "usage": "保存答疑、练习、资源访问等学习行为"},
            {"name": "resource_feedback", "label": "资源反馈表", "count": _table_count("resource_feedback"), "usage": "保存学生对资源的评分和反馈"},
            {"name": "generation_batch", "label": "资源生成批次表", "count": _table_count("generation_batch"), "usage": "保存画像快照、资源计划、trace ID和批次状态"},
            {"name": "agent_execution", "label": "智能体执行轨迹表", "count": _table_count("agent_execution"), "usage": "保存各智能体状态、评分、返工次数和耗时"},
            {"name": "resource_source", "label": "资源来源关联表", "count": _table_count("resource_source"), "usage": "保存每项资源对应的RAG教材片段"},
        ]
        ai_status = {
            "mock_ai": config.MOCK_AI,
            "mode": "模拟演示模式" if config.MOCK_AI else "真实讯飞模型模式",
            "spark": {
                "configured": bool(config.XFYUN_APP_ID and config.XFYUN_API_KEY and config.XFYUN_API_SECRET),
                "app_id": _mask(config.XFYUN_APP_ID),
                "api_key": _mask(config.XFYUN_API_KEY),
                "api_secret": _mask(config.XFYUN_API_SECRET),
                "domain": config.XFYUN_SPARK_DOMAIN,
                "url": config.XFYUN_SPARK_URL,
            },
            "seedance": {
                "configured": bool(config.SEEDANCE_API_KEY and config.SEEDANCE_API_URL),
                "api_key": _mask(config.SEEDANCE_API_KEY),
                "url": config.SEEDANCE_API_URL or "未配置",
            },
            "content_audit": {
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
        return fail("系统状态查询失败，请检查 MySQL 是否启动以及 .env 数据库配置是否正确", 500, {"error": str(exc)})


@system_bp.post("/test-ai")
@login_required
def test_ai():
    try:
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt") or "请用一句话说明你正在连接人工智能导论学习系统。")
        spark_result = spark_chat(prompt)
        audit_result = content_audit("人工智能导论课程学习")
        seedance_result = "未测试"
        if payload.get("test_video"):
            seedance_result = see_dance_generate("请生成一个30秒人工智能导论课程介绍视频")
        return success(
            {
                "mode": "模拟演示模式" if config.MOCK_AI else "真实讯飞模型模式",
                "mock_ai": config.MOCK_AI,
                "spark_result": spark_result,
                "content_audit_passed": audit_result,
                "seedance_result": seedance_result,
            },
            "AI 连通性测试完成",
        )
    except Exception as exc:
        return fail("AI 连通性测试失败", 500, {"error": str(exc)})
