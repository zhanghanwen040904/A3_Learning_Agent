from flask import Blueprint, request

from ai.agents import ProfileAgent
from ai.spark_api import content_audit
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

profile_bp = Blueprint("profile", __name__)
profile_agent = ProfileAgent()

PROFILE_FIELDS = [
    "knowledge_level",
    "study_style",
    "weak_points",
    "study_goal",
    "study_time_prefer",
    "course_progress",
]


@profile_bp.post("/create")
@login_required
def create_profile():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["dialogue"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        dialogue = str(payload["dialogue"])
        if not content_audit(dialogue):
            return fail("学生对话未通过讯飞内容审核", 403)

        profile = profile_agent.analyze(dialogue)
        data = {"user_id": request.user_id, **{field: profile.get(field, "待进一步观察") for field in PROFILE_FIELDS}}
        mysql_db.upsert_by_unique_key("student_profile", data, update_fields=PROFILE_FIELDS)
        return success(data, "画像创建成功")
    except Exception as exc:
        return fail("画像创建失败", 500, {"error": str(exc)})


@profile_bp.post("/update")
@login_required
def update_profile():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["learning_data"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        learning_data = str(payload["learning_data"])
        if not content_audit(learning_data):
            return fail("学习数据未通过讯飞内容审核", 403)

        old_profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (request.user_id,)) or {}
        dialogue = f"历史画像：{old_profile}\n最新学习数据：{learning_data}"
        profile = profile_agent.analyze(dialogue)
        data = {field: profile.get(field, "待进一步观察") for field in PROFILE_FIELDS}
        affected = mysql_db.update("student_profile", data, "user_id=%s", (request.user_id,))
        if affected == 0:
            mysql_db.insert("student_profile", {"user_id": request.user_id, **data})
        return success({"user_id": request.user_id, **data}, "画像更新成功")
    except Exception as exc:
        return fail("画像更新失败", 500, {"error": str(exc)})


@profile_bp.get("/")
@login_required
def get_my_profile():
    try:
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (request.user_id,))
        return success(profile or {}, "查询成功")
    except Exception as exc:
        return fail("画像查询失败", 500, {"error": str(exc)})


@profile_bp.get("/<int:user_id>")
@login_required
def get_profile(user_id: int):
    try:
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s", (request.user_id,))
        return success(profile or {}, "查询成功")
    except Exception as exc:
        return fail("画像查询失败", 500, {"error": str(exc)})
