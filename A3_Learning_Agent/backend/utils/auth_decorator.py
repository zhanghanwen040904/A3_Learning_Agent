from functools import wraps

from flask import request

from utils import fail
from utils.jwt_utils import verify_token


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "").strip()
        if not auth_header:
            return fail("请先登录", 401)

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return fail("登录凭证格式错误", 401)

        user_info = verify_token(parts[1])
        if not user_info:
            return fail("登录已过期，请重新登录", 401)

        request.user_id = user_info["user_id"]
        request.username = user_info["username"]
        return func(*args, **kwargs)

    return wrapper
