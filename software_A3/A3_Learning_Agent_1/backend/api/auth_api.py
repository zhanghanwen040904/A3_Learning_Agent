from flask import Blueprint, request
from werkzeug.security import check_password_hash, generate_password_hash

from db import mysql_db
from utils import fail, require_fields, success
from utils.jwt_utils import generate_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    """用户注册接口。

    功能：创建系统登录用户，密码使用 Werkzeug 哈希存储。
    输入：JSON，包含 username、password。
    输出：统一 JSON，data 中包含用户 ID、用户名和 token。
    """
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["username", "password"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        username = str(payload["username"]).strip()
        password = str(payload["password"])
        if len(username) < 2 or len(password) < 6:
            return fail("用户名至少2位，密码至少6位", 400)

        exists = mysql_db.query_one("SELECT id FROM `user` WHERE username=%s", (username,))
        if exists:
            return fail("用户名已存在", 409)

        user_id = mysql_db.insert("user", {"username": username, "password": generate_password_hash(password)})
        token = generate_token(user_id, username)
        return success({"id": user_id, "username": username, "token": token}, "注册成功")
    except Exception as exc:
        return fail("注册失败", 500, {"error": str(exc)})


@auth_bp.post("/login")
def login():
    """用户登录接口。

    功能：校验用户名和密码，返回用户基础信息和 JWT token。
    输入：JSON，包含 username、password。
    输出：统一 JSON，data 中包含用户 ID、用户名和 token。
    """
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["username", "password"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        user = mysql_db.query_one("SELECT * FROM `user` WHERE username=%s", (str(payload["username"]).strip(),))
        if not user or not check_password_hash(user["password"], str(payload["password"])):
            return fail("用户名或密码错误", 401)

        token = generate_token(user["id"], user["username"])
        return success({"id": user["id"], "username": user["username"], "token": token}, "登录成功")
    except Exception as exc:
        return fail("登录失败", 500, {"error": str(exc)})
