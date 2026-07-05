import json
import queue
import re
import threading
from pathlib import Path

from flask import Blueprint, Response, request, send_file, stream_with_context
from werkzeug.utils import safe_join

from ai.agents import agent_manager
from ai.rag import generated_kb_dir
from config import PROJECT_ROOT
from importlib import import_module
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.jwt_utils import verify_token
from utils.profile_session import resolve_profile_session

_llm_api = import_module("ai.llm_api")
audit_content = getattr(_llm_api, "audit_content")

if hasattr(_llm_api, "llm_chat"):
    llm_chat = getattr(_llm_api, "llm_chat")
elif hasattr(_llm_api, "PlatformLLM"):
    def llm_chat(prompt: str) -> str:
        return getattr(_llm_api, "PlatformLLM")().invoke(prompt)
else:
    raise ImportError("ai.llm_api 中缺少 llm_chat 或 PlatformLLM，无法进行模型文本生成")

content_audit = audit_content
spark_chat = llm_chat
resource_bp = Blueprint("resource", __name__)
IMAGE_PATTERN = re.compile(r"(?:[A-Za-z]:\\[^\n\r，,；;）)]+|images[\\/][^\n\r，,；;）)]+)\.(?:png|jpg|jpeg|webp|gif)", re.IGNORECASE)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_DIR = PROJECT_ROOT / "rag_data" / "videos"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".m4v"}
VIDEO_KEYWORDS = {
    "软件危机": ["软件危机"],
    "软件工程": ["软件工程", "方法学"],
    "软件生命周期": ["软件生命周期", "瀑布模型", "快速原型", "增量模型", "螺旋模型", "喷泉模型", "软件过程"],
    "可行性研究": ["可行性研究", "成本效益", "可行性研究分析"],
    "需求分析": ["需求分析", "需求收集", "分析建模", "ER图", "数据范式", "状态转换图", "验证需求", "形式化说明技术"],
    "数据流图": ["系统流程图", "数据流图", "数据字典"],
    "总体设计": ["总体设计", "耦合", "内聚", "启发式规则", "层次图", "结构图", "结构化设计", "变换分析", "事务分析", "模块"],
    "详细设计": ["详细设计", "结构化程序", "用户界面设计", "PAD图", "判定树", "PDL", "程序复杂度"],
    "编码实现": ["编码"],
    "软件测试": ["测试", "测试目标", "单元测试", "系统测试", "确认测试", "调试"],
    "软件维护": ["维护", "维护工作"],
    "练习": ["习题课"],
}
FORBIDDEN_DOC_FIELDS = {
    "query",
    "knowledge_base_dir",
    "retrieved_chunks",
    "knowledge_tree",
    "images",
    "generation_rules",
    "debug",
    "prompt",
    "raw_request",
    "raw_response",
    "system_prompt",
    "user_prompt",
}


def _safe_json_loads(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _video_id(path: Path) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_-]+", "_", path.stem).strip("_") or path.stem


def _list_local_videos() -> list[dict]:
    if not VIDEO_DIR.exists():
        return []
    videos = []
    for path in sorted(VIDEO_DIR.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        stem = path.stem.strip()
        title = re.sub(r"^\d+\s*", "", stem).strip() or stem
        videos.append(
            {
                "id": _video_id(path),
                "title": title,
                "file_name": path.name,
                "url": f"/api/resource/video/{_video_id(path)}",
                "content_type": "video/mp4" if path.suffix.lower() == ".mp4" else "video/*",
            }
        )
    return videos


def _video_score(video: dict, text: str) -> int:
    title = str(video.get("title") or "")
    file_name = str(video.get("file_name") or "")
    haystack = f"{title} {file_name}"
    score = 0
    compact_text = re.sub(r"[\s_\-（）()]+", "", text)
    compact_title = re.sub(r"[\s_\-（）()]+", "", haystack)
    for concept, keywords in VIDEO_KEYWORDS.items():
        if concept in text:
            for keyword in keywords:
                if keyword in haystack or keyword in compact_title:
                    score += 12
        for keyword in keywords:
            if keyword in text and keyword in haystack:
                score += 8
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text):
        if token and (token in haystack or token in compact_title):
            score += 3
    if title and title in text:
        score += 10
    if "习题" in haystack and any(token in text for token in ["练习", "测评", "巩固", "题"]):
        score += 6
    return score


def match_local_videos(text: str, limit: int = 2) -> list[dict]:
    videos = _list_local_videos()
    ranked = sorted(
        [{**video, "score": _video_score(video, text)} for video in videos],
        key=lambda item: (item["score"], item["title"]),
        reverse=True,
    )
    selected = [item for item in ranked if item["score"] > 0][:limit]
    if not selected and videos:
        selected = videos[:limit]
    return selected


def build_local_video_resource(stage: dict, user_id: int | None = None, session_id: int | None = None) -> dict | None:
    text = " ".join(
        str(part or "")
        for part in [stage.get("title"), stage.get("goal"), " ".join(stage.get("points") or []), stage.get("raw")]
    )
    videos = match_local_videos(text, limit=2)
    if not videos:
        return None
    primary = videos[0]
    points = stage.get("points") or []
    title = f"{stage.get('title') or '当前阶段'}・配套教学视频"
    content_lines = [
        f"# {title}",
        "",
        "本视频资源来自课程本地视频库，已根据当前阶段目标和知识点自动匹配。",
        "",
        "## 推荐观看顺序",
    ]
    for index, video in enumerate(videos, start=1):
        content_lines.append(f"{index}. {video['title']}")
    content_lines.extend(
        [
            "",
            "## 学习建议",
            "- 先带着阶段目标观看视频，记录不理解的术语。",
            "- 再回到讲解文档和思维导图，对照概念、流程和阶段产物。",
            "- 最后完成阶段练习，检查能否迁移应用。",
        ]
    )
    return {
        "id": f"local-video-{stage.get('index') or stage.get('stage_index') or primary['id']}",
        "user_id": user_id,
        "profile_session_id": session_id,
        "resource_type": "video",
        "title": title,
        "content": "\n".join(content_lines),
        "knowledge_points": points,
        "personalization": "根据当前学习阶段知识点从本地视频资源库自动匹配。",
        "quality_score": 88,
        "audit_status": "passed",
        "agent_name": "LocalVideoResource",
        "metadata": {"videos": videos, "video_url": primary.get("url"), "stage": stage},
        "video_url": primary.get("url"),
        "type_label": "教学短视频",
        "sources": [],
    }


def _normalize_compare_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("　", " ")
    text = re.sub(r"[\s\-_—–·•，。！？；：、,.!?;:()\[\]{}<>《》“”\"'`~]+", "", text)
    return text


def _safe_list(value):
    return value if isinstance(value, list) else []


def _dedupe_list(items, key_fn):
    seen = set()
    result = []
    for item in items or []:
        if not item:
            continue
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _pick_text(mapping: dict, *keys, default=""):
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _normalize_section_path(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[>/|｜]", value) if part.strip()]
    return []


def _normalize_learning_location(value, section_path=None, pages=None):
    path = _normalize_section_path(section_path)
    base = value if isinstance(value, dict) else {}
    unit = str(base.get("unit") or (path[0] if len(path) > 0 else "")).strip()
    chapter = str(base.get("chapter") or (path[1] if len(path) > 1 else "")).strip()
    section = str(base.get("section") or (path[2] if len(path) > 2 else "")).strip()
    subsection = str(base.get("subsection") or (path[3] if len(path) > 3 else "")).strip()
    normalized_pages = pages if isinstance(pages, list) else _safe_list(base.get("pages"))
    return {
        "unit": unit,
        "chapter": chapter,
        "section": section,
        "subsection": subsection,
        "path": [item for item in [unit, chapter, section, subsection] if item],
        "path_text": " > ".join([item for item in [unit, chapter, section, subsection] if item]),
        "pages": normalized_pages,
    }


def _safe_evidence_item(item):
    if not isinstance(item, dict):
        return None
    title = str(_pick_text(item, "title")).strip()
    section_path = _normalize_section_path(_pick_text(item, "section_path", "sectionpath"))
    learning_location = _normalize_learning_location(
        _pick_text(item, "learning_location"),
        section_path=section_path,
        pages=_safe_list(_pick_text(item, "pages")),
    )
    content_preview = str(_pick_text(item, "content_preview", "content", default="")).strip()
    if not title and not content_preview:
        return None
    return {
        "title": title or "未命名知识点",
        "content_preview": content_preview[:220],
        "section_path": section_path,
        "learning_location": learning_location,
        "pages": _safe_list(_pick_text(item, "pages")),
        "source_file": str(_pick_text(item, "source_file", "source", default="")).strip(),
    }


def _build_student_context(evidence_items):
    first = evidence_items[0] if evidence_items else {}
    location = _normalize_learning_location(
        _pick_text(first, "learning_location"),
        section_path=_pick_text(first, "section_path"),
        pages=_pick_text(first, "pages", default=[]),
    )
    return {
        "currentunit": location.get("unit", ""),
        "currentchapter": location.get("chapter", ""),
        "currentsection": location.get("section", ""),
        "currentpage": location.get("pages", []),
        "path": location.get("path", []),
        "path_text": location.get("path_text", ""),
    }


def _clean_explanation_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r"(?im)^\s*(标题|章节路径|章節路径|页码|教材页码|内容|知识点|学习步骤|考查重点|输入|输出|案例)\s*[：:]\s*", "", value)
    value = re.sub(r"(?im)^\s*当前(主知识点|学习位置)\s*[：:]\s*", "", value)
    value = re.sub(r"(?im)^\s*教材依据\d*\s*[：:]\s*", "", value)
    value = re.sub(r"结合课程知识库内容可知[：:]?", "", value)
    value = re.sub(r"(?im)^\s*软件工程\s*/\s*.+$", "", value)
    value = re.sub(r"(?im)^\s*章节路径\s*[：:]?\s*.+$", "", value)
    value = re.sub(r"(?im)^\s*页码\s*[：:]?\s*[\d,，、\-\s]+$", "", value)
    value = re.sub(r"(?im)^\s*标题\s*[：:]?\s*.+$", "", value)
    value = value.replace("该逻辑模型是以后设计和实现目标系统的基。", "该逻辑模型是以后设计和实现目标系统的基础。")
    value = re.sub(r"软\s+件", "软件", value)
    value = re.sub(r"问\s+题\s+定\s+义", "问题定义", value)
    value = re.sub(r"可\s+行\s+性\s+研\s+究", "可行性研究", value)
    value = re.sub(r"需\s+求\s+分\s+析", "需求分析", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip(" \n：:")


def _build_primary_evidence(evidence_items):
    primary = evidence_items[0] if evidence_items else {}
    support = []
    for item in evidence_items[1:4]:
        support.append(
            {
                "title": item.get("title", ""),
                "content_preview": item.get("content_preview", ""),
                "section_path": item.get("section_path", []),
                "pages": item.get("pages", []),
            }
        )
    return primary, support


def _rewrite_main_explanation(payload, evidence_items):
    primary, support = _build_primary_evidence(evidence_items)
    if not primary:
        return _clean_explanation_text(payload.get("main_explanation"))

    primary_title = str(primary.get("title") or "").strip()
    primary_content = _clean_explanation_text(primary.get("content_preview") or "")
    support_blocks = []
    for item in support:
        title = str(item.get("title") or "").strip()
        content = _clean_explanation_text(item.get("content_preview") or "")
        if not title and not content:
            continue
        lines = []
        if title:
            lines.append(f"标题：{title}")
        if item.get("section_path"):
            lines.append(f"章节：{' / '.join(item.get('section_path') or [])}")
        if item.get("pages"):
            lines.append(f"页码：{'、'.join(str(x) for x in (item.get('pages') or []))}")
        if content:
            lines.append(f"内容：{content}")
        support_blocks.append("\n".join(lines))

    prompt = f"""
你是软件工程教材讲解整理助手。
请只依据教材片段，围绕一个主知识点生成一段适合学生阅读的自然讲解。

要求：
1. 只围绕“{primary_title}”展开，不要把多个知识点并列罗列成检索结果。
2. 按这个逻辑组织内容：它在软件工程流程中的位置 -> 它要解决什么问题 -> 它依赖什么输入或会产出什么结果 -> 它为什么重要以及会影响哪些后续阶段。
3. 语言要像老师讲解教材，连贯、自然、正式，不要出现“标题、章节路径、页码、内容”等标签。
4. 不要照抄原文，不要把多个教材片段机械拼接，不要重复知识点名称。
5. 如果教材中体现了先后顺序，要明确写出“先……再……最后……”这样的递进关系。
6. 不要输出列表、JSON、调试信息、来源字段，只输出最终讲解正文。

主知识点：
标题：{primary_title}
教材内容：{primary_content}

补充教材片段：
{chr(10).join(support_blocks) if support_blocks else "无"}
""".strip()

    try:
        rewritten = spark_chat(prompt)
        rewritten = _clean_explanation_text(rewritten)
        return rewritten or primary_content
    except Exception:
        return primary_content


def _sanitize_core_concepts(payload, evidence_items):
    concepts = []
    for item in _safe_list(payload.get("core_concepts")):
        if not isinstance(item, dict):
            continue
        name = str(_pick_text(item, "name", "title")).strip()
        if not name:
            continue
        concepts.append(
            {
                "name": name,
                "definition": str(_pick_text(item, "definition", "content", default="")).strip(),
                "why_it_matters": str(_pick_text(item, "why_it_matters", default="")).strip(),
                "example": str(_pick_text(item, "example", default="")).strip(),
                "common_misunderstanding": str(_pick_text(item, "common_misunderstanding", default="")).strip(),
            }
        )
    if not concepts:
        for evidence in evidence_items[:6]:
            concepts.append(
                {
                    "name": evidence["title"],
                    "definition": evidence["content_preview"],
                    "why_it_matters": "",
                    "example": "",
                    "common_misunderstanding": "",
                }
            )
    else:
        primary, _ = _build_primary_evidence(evidence_items)
        if primary and not any(_normalize_compare_text(item.get("name")) == _normalize_compare_text(primary.get("title")) for item in concepts):
            concepts.insert(
                0,
                {
                    "name": primary.get("title", ""),
                    "definition": primary.get("content_preview", ""),
                    "why_it_matters": "",
                    "example": "",
                    "common_misunderstanding": "",
                },
            )
    return _dedupe_list(concepts, lambda item: _normalize_compare_text(item.get("name")))


def _sanitize_explanations(payload, evidence_items):
    items = []
    for item in _safe_list(payload.get("knowledge_explanation")):
        if not isinstance(item, dict):
            continue
        title = str(_pick_text(item, "title", "name")).strip()
        explanation = str(_pick_text(item, "explanation", "content", default="")).strip()
        if not title and not explanation:
            continue
        items.append(
            {
                "title": title or "知识点讲解",
                "explanation": explanation,
                "process": [str(step).strip() for step in _safe_list(item.get("process")) if str(step).strip()],
                "input_output": item.get("input_output") if isinstance(item.get("input_output"), dict) else None,
                "example": str(_pick_text(item, "example", default="")).strip(),
                "exam_focus": str(_pick_text(item, "exam_focus", default="")).strip(),
            }
        )
    if not items:
        for evidence in evidence_items[:6]:
            items.append(
                {
                    "title": evidence["title"],
                    "explanation": evidence["content_preview"],
                    "process": [],
                    "input_output": None,
                    "example": "",
                    "exam_focus": "",
                }
            )
    else:
        for item in items:
            item["explanation"] = _clean_explanation_text(item.get("explanation"))
    primary, _ = _build_primary_evidence(evidence_items)
    if primary and not any(_normalize_compare_text(item.get("title")) == _normalize_compare_text(primary.get("title")) for item in items):
        items.insert(
            0,
            {
                "title": primary.get("title", ""),
                "explanation": _clean_explanation_text(primary.get("content_preview", "")),
                "process": [],
                "input_output": None,
                "example": "",
                "exam_focus": "",
            },
        )
    return _dedupe_list(items, lambda item: _normalize_compare_text(item.get("title")))


def _sanitize_mistakes(payload, evidence_items):
    mistakes = []
    for item in _safe_list(payload.get("mistakes")):
        if not isinstance(item, dict):
            continue
        title = str(_pick_text(item, "mistake_title", "mistake", "title")).strip()
        if not title:
            continue
        mistakes.append(
            {
                "mistake_title": title,
                "mistake": title,
                "reason": str(_pick_text(item, "reason", default="")).strip(),
                "correction": str(_pick_text(item, "correction", default="")).strip(),
                "example": str(_pick_text(item, "example", default="")).strip(),
            }
        )
    if not mistakes and evidence_items:
        merged = " ".join(item.get("content_preview", "") for item in evidence_items)
        if "可行性研究" in merged:
            mistakes = [
                {"mistake_title": "把可行性研究等同于需求分析", "mistake": "把可行性研究等同于需求分析", "reason": "两者阶段目标不同，可行性研究先判断项目是否值得做、能否做。", "correction": "先评估技术、经济、操作可行性，再进入需求分析。", "example": ""},
                {"mistake_title": "只关注技术可行性", "mistake": "只关注技术可行性", "reason": "教材通常同时强调经济可行性和操作可行性。", "correction": "至少从技术、经济、操作三个维度综合判断。", "example": ""},
                {"mistake_title": "误以为此阶段要完成详细设计", "mistake": "误以为此阶段要完成详细设计", "reason": "可行性研究用于决策支持，不负责详细设计。", "correction": "本阶段输出应是可行性分析结论与建议。", "example": ""},
            ]
    return _dedupe_list(mistakes, lambda item: _normalize_compare_text(item.get("mistake_title") or item.get("mistake")))


def _sanitize_learningresources(evidence_items):
    return _dedupe_list(
        [
            {
                "title": item["title"],
                "content_preview": item["content_preview"],
                "section_path": item["section_path"],
                "learning_location": item["learning_location"],
                "pages": item["pages"],
                "source_file": item["source_file"],
            }
            for item in evidence_items
        ],
        lambda item: "{}|{}".format(
            _normalize_compare_text(item.get("title")),
            _normalize_compare_text(" > ".join(item.get("section_path") or [])),
        ),
    )


def _sanitize_doc_payload(resource: dict) -> dict:
    payload = _extract_resource_json(resource)
    if not payload:
        content = str(resource.get("content") or "").strip()
        if content:
            resource["content"] = "未检索到对应知识库片段。"
        return resource

    for key in list(payload.keys()):
        if key in FORBIDDEN_DOC_FIELDS:
            payload.pop(key, None)

    metadata = _safe_json_loads(resource.get("metadata"), {})
    evidence_source = _safe_list(metadata.get("evidence"))
    payload_evidence = _safe_list(payload.get("learningresources"))
    evidence_items = _dedupe_list(
        [item for item in [_safe_evidence_item(raw) for raw in (evidence_source or payload_evidence)] if item],
        lambda item: "{}|{}".format(
            _normalize_compare_text(item.get("title")),
            _normalize_compare_text(" > ".join(item.get("section_path") or [])),
        ),
    )

    if not evidence_items:
        empty_payload = {
            "resourcetype": "doc",
            "resourcetitle": str(payload.get("resourcetitle") or resource.get("title") or "课程讲解文档"),
            "overview": {"title": str(resource.get("title") or "课程讲解文档"), "content": "未检索到对应知识库片段。"},
            "studentcontext": {"currentunit": "", "currentchapter": "", "currentsection": "", "currentpage": []},
            "core_concepts": [],
            "knowledge_explanation": [],
            "mistakes": [],
            "learningresources": [],
            "summary": {"one_sentence": "未检索到对应知识库片段。", "key_takeaways": []},
            "self_check": [],
        }
        metadata["debug"] = {"empty_retrieval": True}
        resource["metadata"] = metadata
        resource["content"] = json.dumps(empty_payload, ensure_ascii=False)
        return resource

    payload["studentcontext"] = _build_student_context(evidence_items)
    payload["learningresources"] = _sanitize_learningresources(evidence_items)
    payload["core_concepts"] = _sanitize_core_concepts(payload, evidence_items)
    payload["knowledge_explanation"] = _sanitize_explanations(payload, evidence_items)
    payload["mistakes"] = _sanitize_mistakes(payload, evidence_items)
    payload["main_explanation"] = _rewrite_main_explanation(payload, evidence_items)
    if not payload["main_explanation"] and evidence_items:
        payload["main_explanation"] = str(evidence_items[0].get("content_preview") or "").strip()
    primary_title = str(evidence_items[0].get("title") or "").strip() if evidence_items else ""
    if primary_title and isinstance(payload.get("knowledge_explanation"), list):
        for item in payload["knowledge_explanation"]:
            if _normalize_compare_text(item.get("title")) == _normalize_compare_text(primary_title):
                item["explanation"] = payload["main_explanation"]
                break
    payload["overview"] = payload.get("overview") if isinstance(payload.get("overview"), dict) else {}
    payload["overview"]["title"] = str(_pick_text(payload["overview"], "title", default=(evidence_items[0].get("title") if evidence_items else resource.get("title") or "课程讲解文档"))).strip()
    payload["overview"]["content"] = payload["main_explanation"].split("\n")[0].strip() if payload["main_explanation"] else "请结合教材依据理解当前知识点。"
    if isinstance(payload.get("summary"), dict):
        key_takeaways = _dedupe_list(_safe_list(payload["summary"].get("key_takeaways")), lambda item: _normalize_compare_text(item))
        payload["summary"]["key_takeaways"] = [str(item).strip() for item in key_takeaways if str(item).strip()]
    resource["metadata"] = metadata
    resource["content"] = json.dumps(payload, ensure_ascii=False)
    return resource


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



def _extract_resource_json(resource: dict) -> dict:
    content = str(resource.get("content") or "").strip()
    if not content:
        return {}
    content = re.sub(r"^\s*```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*```\s*$", "", content)
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(content[start : end + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_learning_image(raw_image, fallback_caption: str = "image") -> dict | None:
    if isinstance(raw_image, str) and raw_image.strip():
        return {"path": raw_image.strip(), "caption": fallback_caption}
    if isinstance(raw_image, dict):
        path = str(raw_image.get("path") or "").strip()
        if path:
            return {
                "path": path,
                "caption": str(raw_image.get("caption") or fallback_caption or "image").strip(),
            }
    return None


def _extract_group_candidates(resource: dict) -> list[dict]:
    data = _extract_resource_json(resource)
    groups = []
    for item in data.get("learningresources") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("source") or "image").strip()
        section = str(item.get("sectionpath") or "").strip()
        source = str(item.get("source") or "").strip()
        content = str(item.get("content") or "").strip()
        images = []
        for raw_image in item.get("images") or []:
            normalized = _normalize_learning_image(raw_image, title or "image")
            if normalized:
                images.append(normalized)
        if images:
            groups.append(
                {
                    "label": title or "image",
                    "section": section,
                    "source": source,
                    "content": content[:400],
                    "images": images[:3],
                }
            )
    return groups


def _looks_irrelevant_image_text(text: str) -> bool:
    low = str(text or "").lower()
    noise_tokens = [
        "contact",
        "contacts",
        "fax",
        "postal code",
        "company",
        "mobile phone",
        "address",
        "country/region",
        "autonumber",
        "work phone",
        "city",
        "state/province",
    ]
    return any(token in low for token in noise_tokens)


def _group_score(resource: dict, group: dict) -> int:
    knowledge_points = _safe_json_loads(resource.get("knowledge_points"), [])
    if not isinstance(knowledge_points, list):
        knowledge_points = [str(knowledge_points)]
    group_text = " ".join(
        [
            str(group.get("label") or ""),
            str(group.get("section") or ""),
            str(group.get("source") or ""),
            str(group.get("content") or ""),
            " ".join(str(img.get("caption") or "") for img in group.get("images") or []),
            " ".join(str(img.get("path") or "") for img in group.get("images") or []),
        ]
    ).lower()
    target_text = " ".join(
        [
            str(resource.get("title") or ""),
            str(resource.get("resource_type") or ""),
            " ".join(str(item) for item in knowledge_points),
        ]
    ).lower()
    score = 0
    for point in knowledge_points:
        point = str(point or "").strip().lower()
        if point and point in group_text:
            score += 10
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", target_text):
        if token and token in group_text:
            score += 2
    if _looks_irrelevant_image_text(group_text):
        score -= 20
    return score


def _select_groups_with_llm(resource: dict, groups: list[dict]) -> list[dict]:
    if not groups:
        return []
    ranked = sorted(groups, key=lambda item: _group_score(resource, item), reverse=True)
    candidates = []
    for index, group in enumerate(ranked[:6], start=1):
        candidates.append(
            {
                "id": index,
                "label": group["label"],
                "section": group["section"],
                "source": group["source"],
                "content": group["content"],
                "image_count": len(group["images"]),
                "paths": [img["path"] for img in group["images"]],
            }
        )
    knowledge_points = _safe_json_loads(resource.get("knowledge_points"), [])
    if not isinstance(knowledge_points, list):
        knowledge_points = [str(knowledge_points)]
    prompt = (
        "You review textbook image groups for a learning resource. "
        "Keep only image groups that directly explain the current knowledge points. "
        "If one image is insufficient and two images together are required to explain the same concept, set mode to pair. "
        "Delete unrelated screenshots, form pages, decorative images, or images unrelated to the knowledge points. "
        "Return strict JSON only.\n\n"
        f"resource_title: {resource.get('title', '')}\n"
        f"resource_type: {resource.get('resource_type', '')}\n"
        f"knowledge_points: {json.dumps(knowledge_points, ensure_ascii=False)}\n"
        f"candidate_groups: {json.dumps(candidates, ensure_ascii=False)}\n\n"
        '{"keep_ids":[1,2],"group_mode":{"1":"pair","2":"single"}}'
    )
    try:
        raw = spark_chat(prompt)
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return ranked[:2]
        data = json.loads(raw[start : end + 1])
        keep_ids = set()
        for item in data.get("keep_ids", []):
            try:
                keep_ids.add(int(item))
            except Exception:
                continue
        modes = data.get("group_mode") or {}
        selected = []
        for index, group in enumerate(ranked[:6], start=1):
            if index not in keep_ids:
                continue
            mode = str(modes.get(str(index)) or modes.get(index) or "single").lower()
            keep_count = 2 if mode == "pair" else 1
            selected.append({**group, "images": group["images"][:keep_count]})
        return selected or ranked[:2]
    except Exception:
        return ranked[:2]


def _strip_image_hint_sections(content: str) -> str:
    text = str(content or "")
    text = re.sub(r"\n+##\s*閰嶅浘寤鸿[\s\S]*?(?=\n##\s+|\Z)", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n+##\s*鐭ヨ瘑搴撻厤鍥綶\s\S]*?(?=\n##\s+|\Z)", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n+閰嶅浘寤鸿[:锛歖[\s\S]*?(?=\n##\s+|\Z)", "\n", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

def _pick_resource_images(resource: dict, limit: int = 4) -> list[dict]:
    groups = _extract_group_candidates(resource)
    if not groups:
        return []

    selected_groups = _select_groups_with_llm(resource, groups)
    images = []
    seen = set()
    for group in selected_groups:
        for image in group.get("images") or []:
            path = str(image.get("path") or "").strip()
            caption = str(image.get("caption") or group.get("label") or "image").strip()
            if not path or path in seen:
                continue
            if _looks_irrelevant_image_text(f"{caption} {path}"):
                continue
            seen.add(path)
            images.append(
                {
                    "caption": caption,
                    "path": path,
                    "group_label": str(group.get("label") or ""),
                    "group_size": len(group.get("images") or []),
                }
            )
            if len(images) >= limit:
                return images
    return images


def _append_images_to_resource(resource: dict) -> dict:
    images = _pick_resource_images(resource)
    metadata = _safe_json_loads(resource.get("metadata"), {})
    metadata["images"] = images
    resource["metadata"] = metadata
    if resource.get("resource_type") == "doc":
        resource = _sanitize_doc_payload(resource)
    if resource.get("resource_type") != "mindmap":
        resource["content"] = _strip_image_hint_sections(str(resource.get("content") or ""))
    return resource
    if not IMAGE_PATTERN.search(content):
        lines = ["", "## 知识库配图"]
        lines.extend(f"- {image['caption']}：{image['path']}" for image in existing_images[:4])
        resource["content"] = content.rstrip() + "\n" + "\n".join(lines)
    return resource


@resource_bp.get("/video/<video_id>")
def serve_local_video(video_id: str):
    videos = {item["id"]: item for item in _list_local_videos()}
    video = videos.get(video_id)
    if not video:
        return fail("视频不存在", 404)
    file_path = safe_join(str(VIDEO_DIR), video["file_name"])
    if not file_path:
        return fail("视频路径无效", 400)
    return send_file(file_path, mimetype=video.get("content_type") or "video/mp4", conditional=True)


@resource_bp.get("/videos")
@login_required
def list_local_videos():
    return success(_list_local_videos(), "本地视频资源查询成功")


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
        if dialogue and not audit_content(dialogue):
            return fail("资源生成输入未通过内容审核", 403)

        latest_path = mysql_db.query_one(
            "SELECT path_content FROM study_path WHERE user_id=%s AND profile_session_id=%s ORDER BY create_time DESC LIMIT 1",
            (user_id, session_id),
        )
        if latest_path and not payload.get("path_content"):
            payload["path_content"] = latest_path.get("path_content")

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
            if content and audit_content(content):
                metadata = _safe_json_loads(item.get("metadata"), {})
                metadata.update(
                    {
                        "format": item.get("format"),
                        "quality": item.get("quality"),
                        "retry_count": item.get("retry_count", 0),
                        "duration_ms": item.get("duration_ms", 0),
                        "video_url": item.get("video_url"),
                        "stage_id": item.get("stage_id"),
                        "stage_index": item.get("stage_index"),
                        "stage_title": item.get("stage_title"),
                        "stage_points": item.get("stage_points", []),
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
        if not any(item.get("resource_type") == "video" for item in resources):
            profile = mysql_db.query_one(
                "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
                (request.user_id, session["id"]),
            ) or {}
            stage = {
                "index": 1,
                "title": profile.get("study_goal") or profile.get("target_course") or "软件工程学习",
                "goal": profile.get("study_goal") or profile.get("weak_points") or "学习软件工程核心知识",
                "points": [item for item in [profile.get("weak_points"), profile.get("error_prone_points"), profile.get("course_progress")] if item],
            }
            video_resource = build_local_video_resource(stage, user_id=request.user_id, session_id=session["id"])
            if video_resource:
                resources.append(video_resource)
        return success(resources, "查询成功")
    except Exception as exc:
        return fail("资源查询失败", 500, {"error": str(exc)})


@resource_bp.get("/<int:user_id>")
@login_required
def list_resources(user_id: int):
    return list_my_resources()


def _persist_stream_result(result: dict, user_id: int, session_id: int) -> dict:
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
        if content and audit_content(content):
            metadata = _safe_json_loads(item.get("metadata"), {})
            metadata.update({"format": item.get("format"), "quality": item.get("quality"), "retry_count": item.get("retry_count", 0), "duration_ms": item.get("duration_ms", 0), "video_url": item.get("video_url"), "stage_id": item.get("stage_id"), "stage_index": item.get("stage_index"), "stage_title": item.get("stage_title"), "stage_points": item.get("stage_points", [])})
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
    return result


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _user_from_stream_request():
    token = request.args.get("token", "").strip()
    if not token:
        auth_header = request.headers.get("Authorization", "").strip()
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    return verify_token(token) if token else None


@resource_bp.get("/generate/stream")
def generate_resources_stream():
    user_info = _user_from_stream_request()
    if not user_info:
        return Response(_sse("error", {"message": "请先登录"}), status=401, mimetype="text/event-stream")

    user_id = user_info["user_id"]
    payload = {key: request.args.get(key) for key in request.args if key != "token"}
    if payload.get("profile_session_id"):
        try:
            payload["profile_session_id"] = int(payload["profile_session_id"])
        except Exception:
            pass

    def stream():
        events = queue.Queue()
        done = object()

        def push(event: dict) -> None:
            events.put(event)

        def worker() -> None:
            try:
                session = resolve_profile_session(user_id, payload, create_if_missing=False)
                if not session:
                    push({"type": "error", "message": "请先新建画像对话并生成画像"})
                    return
                session_id = session["id"]
                profile = mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
                if not profile and not payload.get("dialogue"):
                    push({"type": "error", "message": "当前画像为空，请先生成学生画像，再生成学习资源"})
                    return
                dialogue = str(payload.get("dialogue") or payload.get("learning_need") or "")
                if dialogue and not audit_content(dialogue):
                    push({"type": "error", "message": "资源生成输入未通过内容审核"})
                    return
                latest_path = mysql_db.query_one(
                    "SELECT path_content FROM study_path WHERE user_id=%s AND profile_session_id=%s ORDER BY create_time DESC LIMIT 1",
                    (user_id, session_id),
                )
                if latest_path and not payload.get("path_content"):
                    payload["path_content"] = latest_path.get("path_content")
                result = agent_manager.run_pipeline(dialogue, stored_profile=profile, request_data=payload, event_callback=push)
                saved = _persist_stream_result(result, user_id, session_id)
                push({"type": "result", "message": "资源生成成功", "result": saved})
            except Exception as exc:
                push({"type": "error", "message": "资源生成失败", "error": str(exc)})
            finally:
                events.put(done)

        threading.Thread(target=worker, daemon=True).start()
        yield _sse("open", {"message": "SSE connected"})
        while True:
            event = events.get()
            if event is done:
                yield _sse("close", {"message": "stream closed"})
                break
            event_type = event.get("type", "message")
            yield _sse(event_type, event)

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
