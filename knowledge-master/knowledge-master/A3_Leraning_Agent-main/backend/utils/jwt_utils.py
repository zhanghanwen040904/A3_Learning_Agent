from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt

from config import config


def generate_token(user_id: int, username: str) -> str:
    expire_time = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {
        "user_id": int(user_id),
        "username": username,
        "exp": expire_time,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
        return {"user_id": int(payload["user_id"]), "username": payload["username"]}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None
