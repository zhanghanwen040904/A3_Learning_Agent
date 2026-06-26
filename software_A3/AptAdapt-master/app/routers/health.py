"""健康检查 — 探测各 pipeline 阶段连通性"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db, engine
from ..services.retriever import _get_retriever
from ..config import XFYUN_APPID, XFYUN_API_KEY, DATABASE_URL

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="全链路健康检查")
async def health_check(db: Session = Depends(get_db)):
    """
    探测各阶段连通性，返回每阶段状态。
    不会实际调用 API 产生费用。

    返回各阶段: ok / degraded / fail
    """
    checks = {}

    # 1. 数据库
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "detail": DATABASE_URL}
    except Exception as e:
        checks["database"] = {"status": "fail", "detail": str(e)}

    # 2. API 密钥配置
    if XFYUN_APPID and XFYUN_API_KEY:
        checks["api_keys"] = {"status": "ok", "detail": f"APPID={XFYUN_APPID}"}
    else:
        checks["api_keys"] = {"status": "fail", "detail": "缺少 XFYUN_APPID 或 XFYUN_API_KEY"}

    # 3. Chroma 知识库
    try:
        r = _get_retriever()
        count = r.count
        checks["chroma"] = {
            "status": "ok" if count > 0 else "degraded",
            "detail": f"已入库 {count} 条知识片段" if count > 0 else "知识库为空，请先运行 populate_knowledge_base()",
        }
    except Exception as e:
        checks["chroma"] = {"status": "degraded", "detail": str(e)}

    # 4. 路由注册
    try:
        from ..main import app
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        checks["routes"] = {"status": "ok", "detail": f"已注册 {len(routes)} 条路由"}
    except Exception as e:
        checks["routes"] = {"status": "fail", "detail": str(e)}

    # 汇总
    statuses = [c["status"] for c in checks.values()]
    if "fail" in statuses:
        overall = "degraded"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "ok"

    return {"status": overall, "checks": checks}
