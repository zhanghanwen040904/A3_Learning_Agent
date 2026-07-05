from pathlib import Path

from flask import Blueprint, request, send_file

from ai.rag import build_vector_db, generated_kb_dir, rag_status, retrieve_knowledge_items
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.get("/status")
@login_required
def status():
    try:
        return success(rag_status(), "知识库状态查询成功")
    except Exception as exc:
        return fail("知识库状态查询失败", 500, {"error": str(exc)})


@knowledge_bp.post("/rebuild")
@login_required
def rebuild():
    try:
        payload = request.get_json(silent=True) or {}
        result = build_vector_db(force=bool(payload.get("force", True)))
        return success(result, "知识库重建完成")
    except Exception as exc:
        return fail("知识库重建失败", 500, {"error": str(exc)})


@knowledge_bp.post("/search")
@login_required
def search():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["query"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)
        items = retrieve_knowledge_items(str(payload["query"]), int(payload.get("top_k", 5)))
        return success({"items": items}, "检索成功")
    except Exception as exc:
        return fail("知识库检索失败", 500, {"error": str(exc)})


@knowledge_bp.get("/image")
def image():
    """Serve images extracted from the local generated knowledge base."""
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        return fail("缺少图片路径", 400)
    try:
        image_root = (generated_kb_dir() / "images").resolve()
        path = Path(raw_path)
        if not path.is_absolute():
            path = image_root / raw_path
        image_path = path.resolve()
        if image_root not in image_path.parents and image_path != image_root:
            return fail("图片路径不在知识库图片目录内", 403)
        if not image_path.exists() or image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            return fail("图片不存在或格式不支持", 404)
        return send_file(str(image_path))
    except Exception as exc:
        return fail("图片读取失败", 500, {"error": str(exc)})
