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


def _table_meta(name: str, label: str, usage: str, phase: str, status: str, note: str):
    return {
        "name": name,
        "label": label,
        "count": _table_count(name),
        "usage": usage,
        "phase": phase,
        "status": status,
        "note": note,
    }


@system_bp.get("/status")
@login_required
def status():
    try:
        db_status = mysql_db.query_one("SELECT DATABASE() AS database_name, VERSION() AS version") or {}
        tables = [
            _table_meta("user", "用户表", "保存注册用户与登录账号", "核心在用", "active", "当前登录、权限识别和基础用户体系都依赖该表。"),
            _table_meta("student_profile", "学生画像表", "保存学生画像结果", "核心在用", "active", "学生画像页展示的维度分数、更新轨迹和建议都来自这里。"),
            _table_meta("study_resource", "学习资源表", "保存文档、题目、图解、代码、视频等资源", "核心在用", "active", "当前资源推荐、知识点补充和示例内容主要落在这张表。"),
            _table_meta("study_path", "学习路径表", "保存个性化学习路径", "核心在用", "active", "学习路径编排和阶段推进依赖该表。"),
            _table_meta("quiz_result", "练习结果表", "保存答题结果与反馈", "核心在用", "active", "答题正确率、练习反馈和阶段评估会持续写入这里。"),
            _table_meta("mastery_record", "掌握度表", "保存知识点掌握情况", "核心在用", "active", "画像中的知识基础、知识点掌握等判断依赖该表。"),
            _table_meta("learning_event", "学习行为表", "保存问答、练习、资源访问等记录", "核心在用", "active", "用于追踪真实学习行为，是动态画像更新的重要依据。"),
            _table_meta("resource_feedback", "资源反馈表", "预留给后续资源评分、评论与资源满意度分析", "预留未接入", "planned", "当前版本还没有开放资源评分/评价入口，后端也未接入写入流程，因此数据量为 0 属正常现象。"),
            _table_meta("generation_batch", "生成批次表", "保存资源生成批次信息", "辅助支撑", "partial", "主要用于记录资源生成过程，偏后台管理与追踪。"),
            _table_meta("agent_execution", "智能体执行表", "保存智能体执行轨迹", "辅助支撑", "partial", "用于观察智能体调用链路和执行留痕，当前主要服务调试与排障。"),
            _table_meta("resource_source", "资源来源表", "保存资源和知识片段关联", "辅助支撑", "partial", "用于维护资源来源、知识片段引用关系，属于资源治理支撑数据。"),
        ]
        active_tables = sum(1 for item in tables if item["status"] == "active")
        planned_tables = sum(1 for item in tables if item["status"] == "planned")
        partial_tables = sum(1 for item in tables if item["status"] == "partial")

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
                    "summary": {
                        "total_tables": len(tables),
                        "active_tables": active_tables,
                        "planned_tables": planned_tables,
                        "partial_tables": partial_tables,
                        "resource_feedback_count": next(
                            (item["count"] for item in tables if item["name"] == "resource_feedback"),
                            0,
                        ),
                    },
                },
                "ai": ai_status,
                "project_stage": {
                    "title": "当前版本以学习画像、学习路径、答题评估和资源推荐闭环为主",
                    "description": "现阶段项目已经打通用户、画像、路径、答题、掌握度、学习行为和资源生成的主链路；资源评分与评论能力仍处于预留阶段，因此 resource_feedback 为 0 不代表异常。",
                },
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
