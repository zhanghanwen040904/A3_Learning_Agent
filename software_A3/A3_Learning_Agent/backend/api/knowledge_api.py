from pathlib import Path

from flask import Blueprint, request, send_file

from ai.rag import build_vector_db, generated_kb_dir, rag_status, retrieve_knowledge_items
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

knowledge_bp = Blueprint("knowledge", __name__)
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _compact_image_token(value: str) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _candidate_image_paths(raw_path: str) -> list[Path]:
    """Resolve image paths emitted by the packaged RAG data.

    The generated JSON may contain either the current relative path
    (images/chapter/page_x.jpeg) or an old absolute path from the build
    machine. Keep this resolver tolerant so copied projects still render
    textbook images.
    """
    kb_root = generated_kb_dir().resolve()
    image_root = kb_root / "images"
    normalized = raw_path.strip().strip('"').strip("'").replace("\\", "/")
    candidates: list[Path] = []

    raw_candidate = Path(raw_path)
    if raw_candidate.is_absolute():
        candidates.append(raw_candidate)

    if normalized.startswith("images/"):
        candidates.append(kb_root / normalized)
        candidates.append(image_root / normalized[len("images/") :])

    marker = "/images/"
    if marker in normalized:
        relative_after_images = normalized.split(marker, 1)[1]
        candidates.append(image_root / relative_after_images)

    if not raw_candidate.is_absolute():
        candidates.append(image_root / raw_path)

    unique: list[Path] = []
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def _resolve_image_path(raw_path: str) -> Path | None:
    image_root = (generated_kb_dir() / "images").resolve()
    for image_path in _candidate_image_paths(raw_path):
        inside_image_root = image_path == image_root or image_root in image_path.parents
        if image_path.exists() and image_path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES and inside_image_root:
            return image_path

    normalized = raw_path.strip().replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    folder_hint = _compact_image_token(parts[-2]) if len(parts) >= 2 else ""
    file_hint = _compact_image_token(Path(parts[-1]).stem if parts else normalized)
    if file_hint and image_root.exists():
        best: tuple[int, Path] | None = None
        for image_path in image_root.rglob("*"):
            if not image_path.is_file() or image_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue
            score = 0
            if file_hint == _compact_image_token(image_path.stem):
                score += 20
            elif file_hint in _compact_image_token(image_path.stem):
                score += 10
            if folder_hint and folder_hint in _compact_image_token(image_path.parent.name):
                score += 8
            if score and (best is None or score > best[0]):
                best = (score, image_path.resolve())
        if best:
            return best[1]
    return None


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
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        return fail("缺少图片路径", 400)
    try:
        image_path = _resolve_image_path(raw_path)
        if not image_path:
            return fail("图片不存在或格式不支持", 404)
        return send_file(str(image_path))
    except Exception as exc:
        return fail("图片读取失败", 500, {"error": str(exc)})
