import json
import re
from pathlib import Path

from flask import Blueprint, request

from ai.agents import agent_manager
from ai.rag import generated_kb_dir
from ai.spark_api import content_audit
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

resource_bp = Blueprint("resource", __name__)
IMAGE_PATTERN = re.compile(r"(?:[A-Za-z]:\\[^\n\r，,；;）)]+|images[\\/][^\n\r，,；;）)]+)\.(?:png|jpg|jpeg|webp|gif)", re.IGNORECASE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _safe_json_loads(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_image_ref(path: Path) -> str:
    image_root = (generated_kb_dir() / "images").resolve()
    try:
        relative = path.resolve().relative_to(image_root)
        return "images/" + relative.as_posix()
    except Exception:
        return str(path)


def _chapter_score(folder_name: str, text: str) -> int:
    score = 0
    if not text.strip():
        return score
    compact_folder = re.sub(r"[-_\s]", "", folder_name)
    compact_text = re.sub(r"[-_\s]", "", text)
    if compact_folder and compact_folder in compact_text:
        score += 10
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", folder_name):
        if token in text:
            score += 3
    chapter_match = re.search(r"第\d+章", folder_name)
    if chapter_match and chapter_match.group(0) in text:
        score += 5
    chapter_keywords = {
        "第1章": ["软件工程学概述", "软件危机", "软件生命周期", "sdlc"],
        "第2章": ["可行性研究", "成本效益", "技术可行性", "经济可行性"],
        "第3章": ["需求分析", "需求获取", "需求规格", "数据流图", "用例"],
        "第5章": ["总体设计", "结构化设计", "模块", "体系结构", "事务型", "变换型"],
        "第6章": ["详细设计", "伪码", "判定表", "判定树", "流程图", "pad", "n-s"],
        "第7章": ["实现", "编码", "测试", "单元测试", "集成测试", "调试"],
        "第8章": ["维护", "软件维护", "回归测试", "再工程"],
    }
    if chapter_match:
        for keyword in chapter_keywords.get(chapter_match.group(0), []):
            if keyword.lower() in text.lower():
                score += 4
    return score


def _pick_resource_images(resource: dict, limit: int = 4) -> list[dict]:
    metadata = _safe_json_loads(resource.get("metadata"), {})
    existing_text = "\n".join(
        [
            str(resource.get("content") or ""),
            str(resource.get("personalization") or ""),
            json.dumps(metadata, ensure_ascii=False),
        ]
    )
    if IMAGE_PATTERN.search(existing_text):
        return metadata.get("images") if isinstance(metadata.get("images"), list) else []

    knowledge_points = _safe_json_loads(resource.get("knowledge_points"), [])
    if not isinstance(knowledge_points, list):
        knowledge_points = [str(knowledge_points)]
    sources = resource.get("sources") or []
    source_text = " ".join(str(item.get("source") or item.get("source_name") or "") for item in sources if isinstance(item, dict))
    search_text = " ".join(
        [
            str(resource.get("title") or ""),
            str(resource.get("resource_type") or ""),
            str(resource.get("content") or "")[:500],
            " ".join(str(item) for item in knowledge_points),
            source_text,
        ]
    )

    image_root = generated_kb_dir() / "images"
    if not image_root.exists():
        return []

    chapter_dirs = [path for path in image_root.iterdir() if path.is_dir()]
    scored_dirs = sorted(
        ((path, _chapter_score(path.name, search_text)) for path in chapter_dirs),
        key=lambda item: item[1],
        reverse=True,
    )
    selected_dirs = [path for path, score in scored_dirs if score >= 4][:2]
    if not selected_dirs:
        return []

    images = []
    seen = set()
    for folder in selected_dirs:
        for image_path in sorted(folder.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            ref = _normalize_image_ref(image_path)
            if ref in seen:
                continue
            seen.add(ref)
            images.append({"caption": f"{folder.name} 教材配图", "path": ref})
            if len(images) >= limit:
                return images
    return images


def _append_images_to_resource(resource: dict) -> dict:
    images = _pick_resource_images(resource)
    if not images:
        return resource

    metadata = _safe_json_loads(resource.get("metadata"), {})
    existing_images = metadata.get("images") if isinstance(metadata.get("images"), list) else []
    known = {str(item.get("path") or "") for item in existing_images if isinstance(item, dict)}
    for image in images:
        if image["path"] not in known:
            existing_images.append(image)
            known.add(image["path"])
    metadata["images"] = existing_images
    resource["metadata"] = metadata

    content = str(resource.get("content") or "")
    if not IMAGE_PATTERN.search(content):
        lines = ["", "## 知识库配图"]
        lines.extend(f"- {image['caption']}：{image['path']}" for image in existing_images[:4])
        resource["content"] = content.rstrip() + "\n" + "\n".join(lines)
    return resource


@resource_bp.post("/generate")
@login_required
def generate_resources():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        session = resolve_profile_session(user_id, payload, create_if_missing=False)
        if not session:
            return fail("请先新建画像对话并生成画像", 404)
        session_id = session["id"]
        profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
        if not profile and not payload.get("dialogue"):
            return fail("当前画像为空，请先生成学生画像，再生成学习资源", 404)

        dialogue = str(payload.get("dialogue") or payload.get("learning_need") or "")
        if dialogue and not content_audit(dialogue):
            return fail("资源生成输入未通过内容审核", 403)

        result = agent_manager.run_pipeline(dialogue, stored_profile=profile, request_data=payload)
        batch_id = mysql_db.insert(
            "generation_batch",
            {
                "trace_id": result["trace_id"],
                "user_id": user_id,
                "profile_session_id": session_id,
                "profile_snapshot": json.dumps(result.get("context", {}), ensure_ascii=False),
                "plan": json.dumps(result.get("plan", {}), ensure_ascii=False),
                "status": "completed" if not result.get("errors") else "completed_with_warnings",
                "error_summary": "；".join(result.get("errors", [])),
            },
        )
        saved_resources = []
        for item in result.get("resource_list", []):
            item = _append_images_to_resource(item)
            content = str(item.get("content", ""))
            if content and content_audit(content):
                metadata = _safe_json_loads(item.get("metadata"), {})
                metadata.update(
                    {
                        "format": item.get("format"),
                        "quality": item.get("quality"),
                        "retry_count": item.get("retry_count", 0),
                        "duration_ms": item.get("duration_ms", 0),
                        "video_url": item.get("video_url"),
                    }
                )
                resource_id = mysql_db.insert(
                    "study_resource",
                    {
                        "user_id": user_id,
                        "profile_session_id": session_id,
                        "resource_type": item.get("resource_type", "unknown"),
                        "title": item.get("title", "未命名资源"),
                        "content": content,
                        "batch_id": batch_id,
                        "agent_name": item.get("agent_name"),
                        "knowledge_points": json.dumps(item.get("knowledge_points", []), ensure_ascii=False),
                        "personalization": item.get("personalization"),
                        "quality_score": item.get("quality_score"),
                        "audit_status": "passed" if item.get("quality", {}).get("passed") else "warning",
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                    },
                )
                for source in item.get("sources", []):
                    mysql_db.insert(
                        "resource_source",
                        {
                            "resource_id": resource_id,
                            "source_name": source.get("source", "unknown"),
                            "chunk_index": source.get("chunk_index"),
                            "relevance_score": source.get("score"),
                            "retrieval_mode": source.get("retrieval_mode"),
                        },
                    )
                saved_resources.append({"id": resource_id, **item, "content": content})
        score_by_agent = {item.get("agent_name"): item.get("quality_score") for item in result.get("resource_list", [])}
        for event in result.get("trace", []):
            mysql_db.insert(
                "agent_execution",
                {
                    "batch_id": batch_id,
                    "agent_name": event.get("agent"),
                    "status": event.get("status", "unknown"),
                    "message": event.get("message"),
                    "score": score_by_agent.get(event.get("agent")),
                    "retry_count": event.get("retry_count", 0),
                    "duration_ms": event.get("duration_ms", 0),
                },
            )
        mysql_db.execute("UPDATE generation_batch SET finish_time=NOW() WHERE id=%s", (batch_id,))
        result["resource_list"] = saved_resources or result.get("resource_list", [])
        result["batch_id"] = batch_id
        result["profile_session_id"] = session_id
        return success(result, "资源生成成功")
    except Exception as exc:
        return fail("资源生成失败", 500, {"error": str(exc)})


@resource_bp.get("/")
@login_required
def list_my_resources():
    try:
        session = resolve_profile_session(request.user_id, create_if_missing=False)
        if not session:
            return success([], "暂无画像会话资源")
        profile = mysql_db.query_one(
            "SELECT id FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session["id"]),
        )
        if not profile:
            return success([], "当前画像为空，暂无学习资源")
        resources = mysql_db.query_all(
            """
            SELECT sr.*
            FROM study_resource sr
            INNER JOIN (
                SELECT resource_type, MAX(id) AS max_id
                FROM study_resource
                WHERE user_id=%s AND profile_session_id=%s
                GROUP BY resource_type
            ) latest ON sr.resource_type = latest.resource_type AND sr.id = latest.max_id
            WHERE sr.user_id=%s AND sr.profile_session_id=%s
            ORDER BY FIELD(sr.resource_type, 'doc', 'quiz', 'reading', 'mindmap', 'code', 'video'), sr.id DESC
            """,
            (request.user_id, session["id"], request.user_id, session["id"]),
        )
        for item in resources:
            for field in ("knowledge_points", "metadata"):
                if isinstance(item.get(field), str):
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            item["sources"] = mysql_db.query_all(
                "SELECT source_name AS source, chunk_index, relevance_score AS score, retrieval_mode FROM resource_source WHERE resource_id=%s",
                (item["id"],),
            )
            original_content = str(item.get("content") or "")
            original_metadata = json.dumps(item.get("metadata") or {}, ensure_ascii=False, sort_keys=True)
            _append_images_to_resource(item)
            updated_metadata = json.dumps(item.get("metadata") or {}, ensure_ascii=False, sort_keys=True)
            if str(item.get("content") or "") != original_content or updated_metadata != original_metadata:
                mysql_db.update(
                    "study_resource",
                    {
                        "content": item.get("content"),
                        "metadata": json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                    },
                    "id=%s",
                    (item["id"],),
                )
        return success(resources, "查询成功")
    except Exception as exc:
        return fail("资源查询失败", 500, {"error": str(exc)})


@resource_bp.get("/<int:user_id>")
@login_required
def list_resources(user_id: int):
    return list_my_resources()
