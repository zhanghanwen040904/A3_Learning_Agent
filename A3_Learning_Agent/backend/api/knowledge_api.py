import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from flask import Blueprint, request, send_file

from config import config
from db import mysql_db
from ai.rag import build_vector_db, rag_status, retrieve_knowledge_items
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

knowledge_bp = Blueprint("knowledge", __name__)
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_STATUS_MAP = {"imported": "已导入", "built": "已构建"}


def generated_kb_dir() -> Path:
    return Path(config.RAG_SOURCE_DIR).parent


def _json_dir(name: str) -> Path:
    return generated_kb_dir() / name


def _iter_json_files(folder: Path):
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"))


def _read_json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _preferred_json_path(folder_name: str) -> Path | None:
    files = _iter_json_files(_json_dir(folder_name))
    if not files:
        return None

    preferred_names = {
        "reading_content_json": [
            "学习辅导",
        ],
        "question_bank_json": [
            "rebuilt_question_bank.json",
            "rebuilt",
        ],
        "answers_json": [
            "rebuilt_answers.json",
            "rebuilt",
        ],
    }
    patterns = preferred_names.get(folder_name) or []
    for pattern in patterns:
        for file_path in files:
            if pattern == file_path.name or pattern in file_path.name:
                return file_path
    return files[0]


def _load_first_json(folder_name: str, default):
    preferred = _preferred_json_path(folder_name)
    if preferred:
        try:
            return _read_json_file(preferred)
        except Exception:
            pass
    folder = _json_dir(folder_name)
    for file_path in _iter_json_files(folder):
        if preferred and file_path == preferred:
            continue
        try:
            return _read_json_file(file_path)
        except Exception:
            continue
    return default


def get_chapter_index():
    return _load_first_json("chapter_index_json", {})


def get_knowledge_tree():
    return _load_first_json("knowledge_tree_json", {})


def get_detailed_knowledge_tree():
    return _load_first_json("detailed_knowledge_tree_json", {})


def get_reading_content():
    return _load_first_json("reading_content_json", {})

def get_images_data():
    return _load_first_json("images_json", {})


def _image_url(raw_path: str) -> str:
    return f"/knowledge/image?path={raw_path}"


def _format_knowledge_image(item: dict) -> dict:
    raw_path = str(item.get("path") or item.get("absolute_path") or "").strip()
    return {
        "image_id": item.get("image_id") or raw_path,
        "figure_label": item.get("figure_label") or "",
        "caption": item.get("caption") or "",
        "image_summary": item.get("image_summary") or "",
        "image_type": item.get("image_type") or "",
        "page": item.get("page"),
        "path": raw_path,
        "url": _image_url(raw_path) if raw_path else "",
        "width": item.get("width"),
        "height": item.get("height"),
        "related_knowledge_titles": item.get("related_knowledge_titles") or [],
        "match_confidence": item.get("match_confidence") or item.get("confidence") or 0,
    }


def _section_page_numbers(pages) -> set[int]:
    result: set[int] = set()
    if not isinstance(pages, list):
        return result
    for page in pages:
        if not isinstance(page, dict):
            continue
        try:
            value = page.get("page")
            if value not in (None, ""):
                result.add(int(value))
        except Exception:
            continue
    return result


def _images_for_reading_section(title: str, path: list[str], pages) -> list[dict]:
    payload = get_images_data()
    images = payload.get("images") if isinstance(payload, dict) else []
    if not isinstance(images, list):
        return []

    title_candidates = [_normalize_text(title), *[_normalize_text(item) for item in path or []]]
    title_candidates = [item for item in title_candidates if item]
    page_numbers = _section_page_numbers(pages)
    matched = []
    seen = set()
    for image in images:
        if not isinstance(image, dict) or image.get("keep") is False or image.get("is_knowledge_image") is False:
            continue
        related_titles = [_normalize_text(item) for item in image.get("related_knowledge_titles") or []]
        title_hit = any(
            related and candidate and (related in candidate or candidate in related)
            for related in related_titles
            for candidate in title_candidates
        )
        page_hit = False
        try:
            image_page = int(image.get("page"))
            page_hit = image_page in page_numbers
        except Exception:
            page_hit = False
        if not title_hit and not page_hit:
            continue
        formatted = _format_knowledge_image(image)
        if not formatted["path"] or formatted["image_id"] in seen:
            continue
        seen.add(formatted["image_id"])
        formatted["match_reason"] = "knowledge_title" if title_hit else "page"
        matched.append(formatted)

    return sorted(matched, key=lambda item: (int(item.get("page") or 10**9), item.get("figure_label") or ""))


def _get_reading_tree() -> list[dict]:
    payload = get_reading_content()
    tree = payload.get("tree") if isinstance(payload, dict) else None
    return tree if isinstance(tree, list) else []


def _get_reading_sections_map() -> dict:
    payload = get_reading_content()
    if not isinstance(payload, dict):
        return {}
    sections_by_node_id = payload.get("sections_by_node_id")
    if isinstance(sections_by_node_id, dict):
        return sections_by_node_id
    sections = payload.get("sections")
    if isinstance(sections, list):
        return {item.get("node_id"): item for item in sections if isinstance(item, dict) and item.get("node_id")}
    return {}


def _load_question_bank_items() -> list[dict]:
    payload = _load_first_json("question_bank_json", {})
    rows = payload.get("questions") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    return [item for item in rows if isinstance(item, dict)]


def _load_answers_items() -> list[dict]:
    payload = _load_first_json("answers_json", {})
    rows = payload.get("answers") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    return [item for item in rows if isinstance(item, dict)]


def _group_question_bank_by_resets(items: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    previous_no: int | None = None
    for item in items:
        no = _question_no_int(item.get("question_no"))
        if current and no is not None and previous_no is not None and no < previous_no:
            groups.append(current)
            current = []
        current.append(item)
        if no is not None:
            previous_no = no
    if current:
        groups.append(current)
    return groups


def _answer_no_int(value) -> int | None:
    try:
        text = str(value or "").strip()
        if text.isdigit():
            return int(text)
        match = re.match(r"\s*(\d+)", text)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _group_answers_by_resets(items: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    previous_no: int | None = None
    for item in items:
        no = _answer_no_int(item.get("answer_no"))
        if current and no is not None and previous_no is not None and no < previous_no:
            groups.append(current)
            current = []
        current.append(item)
        if no is not None:
            previous_no = no
    if current:
        groups.append(current)
    return groups


def _answers_for_chapter(chapter_no: int | None) -> list[dict]:
    items = _load_answers_items()
    if not items:
        return []
    if not chapter_no:
        return items
    chapter_key = f"chapter_{chapter_no}"
    keyed = [item for item in items if _clean_chapter_key(item.get("answer_chapter_key") or "") == chapter_key]
    if keyed:
        return keyed
    groups = _group_answers_by_resets(items)
    if 1 <= chapter_no <= len(groups):
        return groups[chapter_no - 1]
    return []


def _extract_sub_answer(answer_text: str, sub_question_no: str = "") -> str:
    text = _clean_text(answer_text)
    target = str(sub_question_no or "").strip()
    if not text or not target:
        return text
    pattern = re.compile(r"[（(]\s*(\d+)\s*[)）]")
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    for index, match in enumerate(matches):
        if match.group(1) != target:
            continue
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return text


def _resolve_answer_from_answers_json(item: dict, chapter_no: int | None = None) -> dict:
    question_no = _question_no_int(item.get("question_no"))
    sub_question_no = str(item.get("sub_question_no") or "").strip()
    if question_no is None:
        return {}
    chapter_answers = _answers_for_chapter(chapter_no)
    answer_item = next((row for row in chapter_answers if _answer_no_int(row.get("answer_no")) == question_no), None)
    if not answer_item:
        return {}
    raw_answer = str(
        answer_item.get("reference_answer")
        or answer_item.get("content")
        or answer_item.get("analysis")
        or ""
    ).strip()
    resolved_answer = _extract_sub_answer(raw_answer, sub_question_no)
    if not resolved_answer:
        return {}
    answer_pages = answer_item.get("pages") or []
    answer_id = answer_item.get("answer_id")
    return {
        "answer": resolved_answer,
        "reference_answer": resolved_answer,
        "analysis": resolved_answer,
        "explanation": resolved_answer,
        "has_answer": True,
        "answer_status": "已按答案库匹配答案",
        "answer_ids": [answer_id] if answer_id else [],
        "answer_link_ids": item.get("answer_link_ids") or [],
        "answer_links": item.get("answer_links") or [],
        "answer_link_confidence": item.get("answer_link_confidence") or 0,
        "answer_link_method": item.get("answer_link_method") or "answers_json_chapter_question_match",
        "answer_pages": answer_pages,
    }


def _workbook_questions_for_chapter(chapter_no: int | None) -> list[dict]:
    items = _load_question_bank_items()
    if not items:
        return []
    if not chapter_no:
        return items
    chapter_key = f"chapter_{chapter_no}"
    keyed = [item for item in items if _clean_chapter_key(item.get("question_chapter_key") or "") == chapter_key]
    if keyed:
        return keyed
    groups = _group_question_bank_by_resets(items)
    if 1 <= chapter_no <= len(groups):
        return groups[chapter_no - 1]
    return []


def _question_no_int(value) -> int | None:
    try:
        text = str(value or "").strip()
        if text.isdigit():
            return int(text)
        match = re.match(r"\s*(\d+)", text)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _chapter_no_from_text(value: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*章", str(value or ""))
    if match:
        return int(match.group(1))
    match = re.search(r"第\s*([一二三四五六七八九十]+)\s*章", str(value or ""))
    if not match:
        return None
    chars = match.group(1)
    numbers = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if chars == "十":
        return 10
    if chars.startswith("十"):
        return 10 + numbers.get(chars[-1], 0)
    if "十" in chars:
        left, _, right = chars.partition("十")
        return numbers.get(left, 1) * 10 + numbers.get(right, 0)
    return numbers.get(chars)


def _extract_exercise_questions_from_text(text: str) -> list[dict]:
    source = str(text or "").replace("\r\n", "\n")
    pattern = re.compile(r"(?m)^\s*(\d+)\s*[.．、]\s*")
    matches = list(pattern.finditer(source))
    questions = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        block = _tidy_reading_text(source[start:end])
        if not block:
            continue
        no = int(match.group(1))
        questions.append({"question_no": str(no), "question_no_int": no, "stem": block, "content": block})
    return questions


def _question_similarity(left: str, right: str) -> float:
    left_text = _clean_text(left)
    right_text = _clean_text(right)
    concept_terms = ["Rational 统一过程", "RUP", "微软过程", "敏捷过程", "软件过程", "软件生命周期模型", "瀑布模型", "快速原型模型", "增量模型", "螺旋模型", "喷泉模型", "软件危机", "软件工程"]
    left_terms = {term for term in concept_terms if term.lower() in left_text.lower()}
    right_terms = {term for term in concept_terms if term.lower() in right_text.lower()}
    if left_terms and right_terms and left_terms.isdisjoint(right_terms):
        return 0.0
    intent_terms = ["优缺点", "适用范围", "适用于", "关系", "区别", "比较", "为什么", "是什么"]
    for intent in intent_terms:
        if intent in left_text and intent not in right_text:
            return 0.0
    a = _normalize_text(left_text)[:240]
    b = _normalize_text(right_text)[:240]
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    score = SequenceMatcher(None, a, b).ratio()
    if left_terms and left_terms & right_terms:
        score += 0.12
    return min(score, 1.0)


def _clean_formula_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = value.replace("$$", "").replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    value = value.replace("\\%", "%").replace("\\{", "{").replace("\\}", "}").replace("\\$", "$")
    value = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\1/\2", value)
    value = re.sub(r"\\(?:mathrm|text|operatorname)\s*\{([^{}]+)\}", r"\1", value)
    value = re.sub(r"\\(?:quad|qquad|space|,|;|!)+", " ", value)
    value = value.replace("\\times", "×").replace("\\cdot", "·").replace("\\leq", "≤").replace("\\geq", "≥")
    value = value.replace("\\neq", "≠").replace("\\approx", "≈").replace("\\infty", "∞")
    value = re.sub(r"\\([A-Za-z]+)", r"\1", value)
    value = re.sub(r"(?<=\d)\s+(?=\d)", "", value)
    value = re.sub(r"\s*([/%=+×·<>≤≥≈])\s*", r" \1 ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.replace("$", "")
    return _tidy_reading_text(value)


def _clean_chapter_key(value: str) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", "", text)


def _chapter_no_from_key(value: str) -> int | None:
    match = re.search(r"chapter_(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def _sort_sub_question_no(value: str) -> tuple[int, str]:
    text = str(value or "").strip()
    match = re.match(r"(\d+)", text)
    if match:
        return (int(match.group(1)), text)
    return (10**9, text)


def _combine_question_group(item: dict) -> dict:
    sub_questions = item.get("sub_questions") or []
    if not sub_questions:
        item["stem"] = _clean_text(item.get("stem") or item.get("content") or "")
        item["content"] = item["stem"]
        item["reference_answer"] = _clean_formula_text(item.get("reference_answer") or item.get("answer") or "")
        item["answer"] = item["reference_answer"]
        item["analysis"] = _clean_formula_text(item.get("analysis") or item.get("explanation") or item["reference_answer"])
        item["explanation"] = item["analysis"]
        return item

    question_parts = []
    answer_parts = []
    base_stem = _clean_text(item.get("stem") or item.get("content") or "")
    if base_stem:
        question_parts.append(base_stem)

    base_answer = _clean_formula_text(item.get("reference_answer") or item.get("answer") or "")
    if base_answer:
        answer_parts.append(base_answer)

    for sub in sub_questions:
        sub_no = str(sub.get("sub_question_no") or "").strip()
        prefix = f"({sub_no})" if sub_no else ""
        sub_stem = _clean_text(sub.get("stem") or "")
        sub_answer = _clean_formula_text(sub.get("reference_answer") or sub.get("answer") or "")
        if sub_stem:
            question_parts.append(f"{prefix}{sub_stem}" if prefix and not sub_stem.startswith(prefix) else sub_stem)
        if sub_answer:
            answer_parts.append(f"{prefix} {sub_answer}".strip() if prefix else sub_answer)

    merged = dict(item)
    merged["stem"] = "\n".join(part for part in question_parts if part).strip()
    merged["content"] = merged["stem"]
    merged["reference_answer"] = "\n".join(part for part in answer_parts if part).strip()
    merged["answer"] = merged["reference_answer"]
    merged["analysis"] = merged["reference_answer"]
    merged["explanation"] = merged["reference_answer"]
    merged["has_answer"] = bool(merged["reference_answer"])
    return merged


def _group_exercise_questions(items: list[dict]) -> list[dict]:
    grouped: dict[int, list[dict]] = {}
    ordered_keys: list[int] = []
    singles: list[dict] = []
    for item in items:
        question_no_int = item.get("question_no_int")
        if question_no_int is None:
            item["sub_questions"] = []
            singles.append(item)
            continue
        if question_no_int not in grouped:
            grouped[question_no_int] = []
            ordered_keys.append(question_no_int)
        grouped[question_no_int].append(item)

    result: list[dict] = []
    result.extend(singles)
    for question_no_int in ordered_keys:
        group = grouped[question_no_int]
        group.sort(key=lambda item: (0 if not str(item.get("sub_question_no") or "").strip() else 1, _sort_sub_question_no(item.get("sub_question_no") or "")))
        if len(group) == 1:
            only = group[0]
            only["sub_questions"] = []
            result.append(only)
            continue

        main_item = next((item for item in group if not str(item.get("sub_question_no") or "").strip()), group[0])
        sub_questions = []
        for item in group:
            if item is main_item and main_item is not group[0]:
                continue
            if item is main_item and not str(main_item.get("sub_question_no") or "").strip():
                continue
            sub_questions.append(
                {
                    "id": item.get("id"),
                    "question_id": item.get("question_id"),
                    "sub_question_no": str(item.get("sub_question_no") or ""),
                    "stem": item.get("stem") or item.get("content") or "",
                    "answer": item.get("answer") or "",
                    "reference_answer": item.get("reference_answer") or "",
                    "analysis": item.get("analysis") or "",
                    "explanation": item.get("explanation") or "",
                    "has_answer": bool(item.get("has_answer")),
                    "answer_status": item.get("answer_status") or "",
                    "answer_pages": item.get("answer_pages") or [],
                    "answer_link_method": item.get("answer_link_method") or "",
                    "question_images": item.get("question_images") or [],
                    "images": item.get("images") or [],
                }
            )

        merged = dict(main_item)
        merged["sub_questions"] = sub_questions
        merged["has_sub_questions"] = bool(sub_questions)
        if main_item is group[0] and str(main_item.get("sub_question_no") or "").strip():
            merged["stem"] = ""
            merged["content"] = ""
        result.append(merged)

    return sorted(
        result,
        key=lambda item: (
            item.get("question_no_int") is None,
            item.get("question_no_int") or 10**9,
            _sort_sub_question_no(item.get("sub_question_no") or ""),
            item.get("id") or "",
        ),
    )


def _chapter_title_defaults() -> dict[int, str]:
    return {
        1: "第 1 章 软件工程概论",
        2: "第 2 章 结构化分析",
        3: "第 3 章 结构化设计",
        4: "第 4 章 结构化实现",
        5: "第 5 章 维护",
        6: "第 6 章 面向对象方法学引论",
        7: "第 7 章 面向对象分析",
        8: "第 8 章 面向对象设计",
        9: "第 9 章 面向对象实现",
        10: "第 10 章 软件项目管理",
    }


def _normalize_numbered_prefix(title: str) -> tuple[int, ...]:
    match = re.match(r"\s*(\d+(?:\.\d+)+)", str(title or ""))
    if not match:
        return ()
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except Exception:
        return ()


def _is_exercise_or_answer_title(title: str) -> bool:
    compact = _clean_chapter_key(title)
    return compact in {"习题", "习题解答"}


def _is_display_noise_title(title: str) -> bool:
    text = _tidy_reading_text(title or "")
    compact = _clean_chapter_key(text)
    if not text:
        return True
    if any(keyword in compact for keyword in ["满分100分", "满分", "注意", "试卷一", "试卷二", "试卷三", "模拟试题参考答案"]):
        return True
    if re.fullmatch(r"[（(]?\d+[)）]?\s*[\u4e00-\u9fa5A-Za-z]+[-—–]+\s*[\u4e00-\u9fa5A-Za-z]+[。.]?\s*0?", compact):
        return True
    if re.fullmatch(r"[（(]?\d+[)）]?.{0,60}0", compact) and "--" in text:
        return True
    return False


def _path_contains_exercise_or_answer(path) -> bool:
    for item in _normalize_path(path or []):
        if _is_exercise_or_answer_title(item):
            return True
    return False


def _infer_reading_chapter_no(node: dict) -> int | None:
    title = _tidy_reading_text(node.get("title") or "")
    path_text = " ".join(_normalize_path(node.get("path") or []))
    if any(keyword in title for keyword in ["附录", "参考文献", "试卷", "模拟试题"]):
        return None
    for candidate in [title, path_text]:
        chapter_no = _chapter_no_from_text(candidate)
        if chapter_no is not None:
            return chapter_no

    numbered = _normalize_numbered_prefix(title)
    if numbered:
        return numbered[0]

    combined = f"{title} {path_text}"
    keyword_map = [
        (10, ["软件项目管理"]),
        (9, ["面向对象实现"]),
        (8, ["面向对象设计"]),
        (7, ["面向对象分析"]),
        (6, ["面向对象方法学引论"]),
        (5, ["维护"]),
        (4, ["结构化实现"]),
        (3, ["结构化设计"]),
        (2, ["结构化分析"]),
        (1, ["软件工程概论", "软件危机", "软件工程", "软件生命周期", "软件过程"]),
    ]
    for chapter_no, keywords in keyword_map:
        if any(keyword in combined for keyword in keywords):
            return chapter_no

    start_page = node.get("start_page")
    if isinstance(start_page, int) and start_page < 27:
        return 1
    return None


def _is_chapter_marker_node(node: dict, chapter_no: int | None = None) -> bool:
    title = _tidy_reading_text(node.get("title") or "")
    inferred = chapter_no if chapter_no is not None else _infer_reading_chapter_no(node)
    if re.search(r"第\s*\d+\s*章", title):
        return True
    if inferred == 2 and title == "结构化分析":
        return True
    if inferred == 10 and title == "软件项目管理":
        return True
    return False


def _iter_tree_nodes_with_parent(nodes: list[dict], parent: dict | None = None):
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        yield node, parent
        yield from _iter_tree_nodes_with_parent(node.get("children") or [], node)


def _clone_chapter_subtree(node: dict, chapter_no: int) -> dict | None:
    if not isinstance(node, dict):
        return None
    title = _tidy_reading_text(node.get("title") or "")
    if not title or _is_exercise_or_answer_title(title) or _is_display_noise_title(title) or _path_contains_exercise_or_answer(node.get("path") or []):
        return None
    inferred = _infer_reading_chapter_no(node)
    if inferred != chapter_no:
        return None

    clone = {**node}
    clone["title"] = title
    clone["path"] = [_tidy_reading_text(item) for item in _normalize_path(node.get("path") or [])]
    clone["children"] = []
    for child in node.get("children") or []:
        child_clone = _clone_chapter_subtree(child, chapter_no)
        if child_clone:
            clone["children"].append(child_clone)
    return clone


def _retitle_path_for_chapter_nodes(nodes: list[dict], root_title: str, chapter_title: str, prefix: list[str] | None = None):
    base_prefix = list(prefix or [root_title, chapter_title])
    for node in nodes:
        node["path"] = [*base_prefix, node.get("title") or ""]
        if node.get("children"):
            _retitle_path_for_chapter_nodes(node["children"], root_title, chapter_title, node["path"])


def _build_restructured_reading_tree(reading_tree: list[dict]) -> list[dict]:
    formatted = _format_reading_tree_nodes(reading_tree)
    if not formatted:
        return []

    original_root = formatted[0]
    root_title = _tidy_reading_text(original_root.get("title") or get_course_name() or "教材资源")
    chapter_map: dict[int, dict] = {}
    chapter_titles = _chapter_title_defaults()

    top_nodes_by_chapter: dict[int, list[dict]] = {}
    for node, parent in _iter_tree_nodes_with_parent(formatted, None):
        if node.get("node_id") == original_root.get("node_id"):
            continue
        title = _tidy_reading_text(node.get("title") or "")
        if not title or _is_exercise_or_answer_title(title) or _is_display_noise_title(title) or _path_contains_exercise_or_answer(node.get("path") or []):
            continue
        chapter_no = _infer_reading_chapter_no(node)
        if chapter_no is None or chapter_no > 10:
            continue
        if title in chapter_titles.values():
            chapter_titles[chapter_no] = title
        if _is_chapter_marker_node(node, chapter_no):
            continue

        if isinstance(parent, dict) and parent.get("node_id") == original_root.get("node_id"):
            top_nodes_by_chapter.setdefault(chapter_no, []).append(node)
            continue

        parent_chapter = _infer_reading_chapter_no(parent) if isinstance(parent, dict) else None
        parent_title = _tidy_reading_text(parent.get("title") or "") if isinstance(parent, dict) else ""
        if parent_chapter != chapter_no or _is_chapter_marker_node(parent or {}, parent_chapter) or _is_exercise_or_answer_title(parent_title):
            top_nodes_by_chapter.setdefault(chapter_no, []).append(node)

    chapter_children = []
    for chapter_no in sorted(top_nodes_by_chapter):
        chapter_title = chapter_titles.get(chapter_no) or f"第 {chapter_no} 章"
        children = []
        for top_node in sorted(top_nodes_by_chapter[chapter_no], key=lambda item: (item.get("start_page") or 10**9, item.get("title") or "")):
            clone = _clone_chapter_subtree(top_node, chapter_no)
            if clone:
                children.append(clone)
        _retitle_path_for_chapter_nodes(children, root_title, chapter_title)
        chapter_children.append(
            {
                "node_id": f"reading_chapter_{chapter_no}",
                "parent_id": original_root.get("node_id"),
                "title": chapter_title,
                "level": 1,
                "path": [root_title, chapter_title],
                "children": children,
                "is_synthetic_chapter": True,
                "reading_chapter_no": chapter_no,
            }
        )

    return [
        {
            **original_root,
            "title": root_title,
            "path": [root_title],
            "children": chapter_children,
        }
    ]

def _normalize_section_path_local(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[>/|｜]", value) if part.strip()]
    return []


def _reading_section_text(section: dict) -> str:
    parts: list[str] = []
    if section.get("full_text"):
        parts.append(str(section.get("full_text") or ""))
    for page in section.get("pages") or []:
        if not isinstance(page, dict):
            continue
        if page.get("text"):
            parts.append(str(page.get("text") or ""))
        for block in page.get("blocks") or []:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block.get("text") or ""))
    return _clean_text("\n".join(parts))


def _extract_reading_answer_terms(stem: str) -> list[str]:
    text = _clean_text(stem)
    terms: list[str] = []
    priority_terms = [
        "软件危机", "软件工程", "可行性研究", "需求分析", "形式化", "总体设计", "详细设计",
        "编码", "测试", "维护", "面向对象", "对象模型", "动态模型", "功能模型", "软件项目管理",
        "成本", "进度", "风险", "CMM", "能力成熟度", "生命周期", "瀑布模型", "原型模型", "螺旋模型",
    ]
    for term in priority_terms:
        if term and term.lower() in text.lower() and term not in terms:
            terms.append(term)
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text):
        if token in {"什么", "哪些", "为什么", "如何", "说明", "简述", "试述", "它有", "它是", "典型", "表现", "原因"}:
            continue
        if token not in terms:
            terms.append(token)
        if len(terms) >= 8:
            break
    return terms


def _section_pages(section: dict) -> list[int]:
    pages: list[int] = []
    for value in [section.get("start_page"), section.get("end_page")]:
        if isinstance(value, int) and value not in pages:
            pages.append(value)
    for page in section.get("pages") or []:
        if isinstance(page, dict) and isinstance(page.get("page"), int) and page.get("page") not in pages:
            pages.append(page.get("page"))
    return sorted(pages)


def _fallback_answer_from_reading_sections(stem: str, exercise_node: dict) -> dict | None:
    sections_map = _get_reading_sections_map()
    if not sections_map:
        return None
    exercise_path = _normalize_section_path_local(exercise_node.get("path") or [])
    chapter_hint = exercise_path[1] if len(exercise_path) > 1 else ""
    terms = _extract_reading_answer_terms(stem)
    if not terms:
        return None

    scored: list[tuple[int, dict, str]] = []
    for section in sections_map.values():
        if not isinstance(section, dict):
            continue
        title = _clean_text(section.get("title") or "")
        if not title or "习题" in title:
            continue
        path = _normalize_section_path_local(section.get("path") or [])
        same_chapter = bool(chapter_hint and chapter_hint in " ".join(path))
        title_has_term = any(term and term in title for term in terms)
        if not same_chapter and not title_has_term:
            continue
        body = _reading_section_text(section)
        if not body:
            continue
        haystack = f"{title}\n{body}"
        score = 0
        if same_chapter:
            score += 8
        for term in terms:
            if term in title:
                score += 12
            if term in body:
                score += 5
        if "为什么" in stem or "原因" in stem:
            if "原因" in title:
                score += 12
            if "原因" in body[:500]:
                score += 4
        if "表现" in stem or "哪些" in stem:
            if "表现" in body[:800] or "典型表现" in body[:800]:
                score += 10
        if "什么是" in stem or "是什么" in stem:
            if "是指" in body[:500] or "称为" in body[:500]:
                score += 8
        if score > 0:
            scored.append((score, section, body))

    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1].get("start_page") or 10**9))
    selected = scored[:3]
    answer_parts: list[str] = []
    pages: list[int] = []
    sources: list[str] = []
    for _, section, body in selected:
        title = _clean_text(section.get("title") or "教材正文")
        excerpt = body[:900].strip()
        if not excerpt:
            continue
        answer_parts.append(f"【{title}】{excerpt}")
        sources.append(title)
        for page in _section_pages(section):
            if page not in pages:
                pages.append(page)
    if not answer_parts:
        return None
    answer = _clean_text("\n\n".join(answer_parts))
    return {
        "answer": answer,
        "reference_answer": answer,
        "analysis": answer,
        "explanation": answer,
        "has_answer": True,
        "answer_status": "已按教材正文匹配答案",
        "answer_link_confidence": None,
        "answer_link_method": "reading_content_keyword_fallback",
        "answer_pages": pages,
        "source": "教材正文知识点：" + "、".join(dict.fromkeys(sources)),
        "related_knowledge_titles": sources,
    }


def _format_bank_question(item: dict, fallback_stem: str = "", chapter_no: int | None = None) -> dict:
    links = item.get("answer_links") or []
    first_link = links[0] if links else {}
    answer = _clean_formula_text(item.get("reference_answer") or item.get("answer") or first_link.get("answer_part_preview") or "")
    analysis = _clean_formula_text(item.get("analysis") or item.get("explanation") or answer)
    stem = _clean_text(item.get("stem") or item.get("content") or fallback_stem)
    formatted = {
        "id": item.get("question_id") or item.get("id") or f"question_{_question_no_int(item.get('question_no')) or len(stem)}",
        "question_id": item.get("question_id") or item.get("id") or "",
        "question_no": str(item.get("question_no") or ""),
        "question_no_int": _question_no_int(item.get("question_no")),
        "sub_question_no": str(item.get("sub_question_no") or ""),
        "stem": stem,
        "content": stem,
        "question_type": item.get("question_type") or "练习题",
        "difficulty_level": item.get("difficulty_level") or item.get("difficulty") or "",
        "answer": answer,
        "reference_answer": answer,
        "analysis": analysis,
        "explanation": analysis,
        "has_answer": bool(answer),
        "answer_status": "已匹配答案" if answer else "暂无匹配答案",
        "answer_ids": item.get("answer_ids") or [],
        "answer_link_ids": item.get("answer_link_ids") or [],
        "answer_links": links,
        "answer_link_confidence": item.get("answer_link_confidence") or first_link.get("match_confidence") or 0,
        "answer_link_method": item.get("answer_link_method") or first_link.get("match_method") or "",
        "pages": item.get("pages") or [],
        "question_images": item.get("question_images") or item.get("images") or [],
        "images": item.get("question_images") or item.get("images") or [],
        "image_count": len(item.get("question_images") or item.get("images") or []),
        "has_question_images": bool(item.get("question_images") or item.get("images")),
        "answer_pages": first_link.get("answer_pages") or [],
        "source": item.get("source_file") or "",
        "related_knowledge_titles": item.get("related_knowledge_titles") or item.get("knowledge_points") or [],
        "sub_questions": [],
        "has_sub_questions": False,
    }
    resolved = _resolve_answer_from_answers_json(item, chapter_no)
    if resolved:
        formatted.update(resolved)
        formatted["answer"] = _clean_formula_text(formatted.get("answer") or "")
        formatted["reference_answer"] = _clean_formula_text(formatted.get("reference_answer") or "")
        formatted["analysis"] = _clean_formula_text(formatted.get("analysis") or "")
        formatted["explanation"] = _clean_formula_text(formatted.get("explanation") or "")
    return formatted


def _exercise_questions_for_reading_node(node_id: str) -> list[dict]:
    sections_map = _get_reading_sections_map()
    node = sections_map.get(node_id) or {}
    title = _clean_text(node.get("title") or "")
    if "习题" not in title:
        return []

    raw_text = "\n".join(str(page.get("text") or "") for page in node.get("pages") or [] if isinstance(page, dict))
    extracted = _extract_exercise_questions_from_text(raw_text)
    chapter_no = _chapter_no_from_text(" ".join([title, *[str(item) for item in node.get("path") or []]]))
    workbook_items = _workbook_questions_for_chapter(chapter_no)
    if workbook_items:
        formatted_items = [_format_bank_question(item, chapter_no=chapter_no) for item in workbook_items]
        return _group_exercise_questions(formatted_items)

    question_bank = _load_question_bank_items()
    bank_by_no: dict[int, list[dict]] = {}
    chapter_items: list[dict] = []
    chapter_key_prefix = f"第{chapter_no}章" if chapter_no else ""
    chapter_key_alt = f"chapter_{chapter_no}" if chapter_no else ""
    for item in question_bank:
        links = item.get("answer_links") or []
        key_text = " ".join(str(link.get("question_chapter_key") or "") for link in links)
        if chapter_key_prefix and chapter_key_prefix not in key_text and chapter_key_alt not in key_text:
            continue
        chapter_items.append(item)
        no = _question_no_int(item.get("question_no"))
        if no is not None:
            bank_by_no.setdefault(no, []).append(item)

    result = []
    used_ids = set()
    for raw in extracted:
        candidates = list(bank_by_no.get(raw["question_no_int"], []))
        for item in chapter_items:
            if item not in candidates:
                candidates.append(item)
        best_item = None
        best_score = 0.0
        for candidate in candidates:
            score = _question_similarity(raw["stem"], candidate.get("stem") or candidate.get("content") or "")
            if score > best_score:
                best_score = score
                best_item = candidate
        if best_item and best_score >= 0.7:
            formatted = _format_bank_question(best_item, raw["stem"], chapter_no)
            formatted["stem"] = raw["stem"]
            formatted["content"] = raw["stem"]
            formatted["match_score"] = round(best_score, 4)
            formatted["answer_status"] = "已按题号匹配答案" if formatted["has_answer"] else "暂无匹配答案"
            result.append(formatted)
            used_ids.add(formatted["question_id"])
        else:
            result.append(
                {
                    "id": f"reading_{node_id}_{raw['question_no_int']}",
                    "question_id": "",
                    "question_no": raw["question_no"],
                    "question_no_int": raw["question_no_int"],
                    "sub_question_no": "",
                    "stem": raw["stem"],
                    "content": raw["content"],
                    "question_type": "练习题",
                    "difficulty_level": "",
                    "answer": "",
                    "reference_answer": "",
                    "analysis": "",
                    "explanation": "",
                    "has_answer": False,
                    "answer_status": "暂无练习册匹配答案",
                    "answer_ids": [],
                    "answer_link_ids": [],
                    "answer_links": [],
                    "answer_link_confidence": 0,
                    "answer_link_method": "",
                    "pages": [],
                    "answer_pages": [],
                    "question_images": [],
                    "images": [],
                    "image_count": 0,
                    "has_question_images": False,
                    "source": "教材习题正文",
                    "related_knowledge_titles": [],
                }
            )

    if result:
        return _group_exercise_questions(result)

    fallback_items = []
    for items in bank_by_no.values():
        for item in items:
            formatted = _format_bank_question(item, chapter_no=chapter_no)
            if formatted["question_id"] not in used_ids:
                fallback_items.append(formatted)
    return _group_exercise_questions(fallback_items)


def _find_tree_node(node_id: str, nodes: list[dict]) -> dict | None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("node_id") == node_id:
            return node
        child = _find_tree_node(node_id, node.get("children") or [])
        if child:
            return child
    return None


def _is_reading_noise_line(line: str) -> bool:
    text = line.strip()
    compact = text.replace(" ", "")
    if not text:
        return False
    if re.fullmatch(r"第\s*\d+\s*页", text):
        return True
    if re.fullmatch(r"\*{0,2}\d+\*{0,2}", text):
        return True
    if re.fullmatch(r"第\s*[0-9一二三四五六七八九十]+\s*章\s*.+", text):
        return True
    if compact in {"软件工程导论（第6版）", "软件工程导论(第6版)", "CHAPTER"}:
        return True
    return False


def _strip_markdown_heading(line: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", line.strip())
    text = re.sub(r"^\*\*(.*?)\**$", r"\1", text)
    return text.strip()


def _find_section_title_line(lines: list[str], section_title: str) -> int:
    title_norm = _normalize_text(section_title)
    if not title_norm:
        return 0
    for index, line in enumerate(lines):
        line_norm = _normalize_text(_strip_markdown_heading(line))
        if line_norm and (title_norm in line_norm or line_norm in title_norm):
            return index + 1
    return 0


def _tidy_reading_text(text: str) -> str:
    value = text.strip()
    value = value.replace("$$", "")
    value = re.sub(r"\\textcircled\{([^}]+)\}", r"\1", value)
    value = re.sub(r"\\cdots", "……", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", value)
    value = re.sub(r"([（(])\s+", r"\1", value)
    value = re.sub(r"\s+([）)，。；：、！？,.!?;:])", r"\1", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


def _format_reading_pages(pages, section_title: str = "") -> list[dict]:
    if not isinstance(pages, list):
        return []
    paragraphs = []
    first_content_page = True
    for item in pages:
        if not isinstance(item, dict):
            continue
        raw_text = str(item.get("text") or "").strip()
        if not raw_text:
            continue
        lines = raw_text.splitlines()
        if first_content_page:
            lines = lines[_find_section_title_line(lines, section_title) :]
            first_content_page = False

        cleaned_lines = []
        for line in lines:
            text = _strip_markdown_heading(line)
            if _is_reading_noise_line(text):
                continue
            cleaned_lines.append(text)

        block = "\n".join(cleaned_lines)
        for paragraph in re.split(r"\n\s*\n+", block):
            text = _tidy_reading_text(paragraph)
            if text and not _is_reading_noise_line(text):
                paragraphs.append({"page": item.get("page"), "text": text})
    return paragraphs


def _attach_images_to_paragraphs(paragraphs: list[dict], images: list[dict]) -> list[dict]:
    if not paragraphs or not images:
        return paragraphs
    page_to_indexes: dict[int, list[int]] = {}
    for index, paragraph in enumerate(paragraphs):
        try:
            page = int(paragraph.get("page"))
        except Exception:
            continue
        page_to_indexes.setdefault(page, []).append(index)
    for image in images:
        try:
            page = int(image.get("page"))
        except Exception:
            continue
        indexes = page_to_indexes.get(page) or []
        if not indexes:
            continue
        target_index = indexes[-1]
        paragraphs[target_index].setdefault("images", []).append(image)
    return paragraphs


def _format_reading_tree_nodes(nodes: list[dict]) -> list[dict]:
    formatted = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        item = {**node}
        item["title"] = _tidy_reading_text(item.get("title") or "")
        item["path"] = [_tidy_reading_text(path_item) for path_item in _normalize_path(item.get("path") or [])]
        item["children"] = _format_reading_tree_nodes(item.get("children") or [])
        formatted.append(item)
    return formatted


def _iter_reading_nodes(nodes: list[dict]):
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        yield node
        yield from _iter_reading_nodes(node.get("children") or [])


def _build_exercise_tree_for_reading(reading_tree: list[dict]) -> list[dict]:
    question_bank = _load_question_bank_items()
    if not question_bank:
        return []

    chapter_groups: dict[int, list[dict]] = {}
    for item in question_bank:
        chapter_no = _chapter_no_from_key(item.get("question_chapter_key") or "")
        if chapter_no is None or chapter_no > 10:
            continue
        chapter_groups.setdefault(chapter_no, []).append(item)
    if not chapter_groups:
        return []

    chapter_title_map = _chapter_title_defaults()
    for node in _iter_reading_nodes(reading_tree):
        title = _tidy_reading_text(node.get("title") or "")
        chapter_no = _infer_reading_chapter_no(node)
        if chapter_no is not None and chapter_no in chapter_title_map and _is_chapter_marker_node(node, chapter_no):
            chapter_title_map[chapter_no] = title

    children = []
    for index in sorted(chapter_groups):
        group = chapter_groups[index]
        if not group:
            continue
        chapter_title = chapter_title_map.get(index) or f"第 {index} 章"
        children.append(
            {
                "node_id": f"exercise_chapter_{index}",
                "parent_id": "exercise_root",
                "title": f"{chapter_title}习题",
                "level": 1,
                "path": ["习题", f"{chapter_title}习题"],
                "children": [],
                "is_exercise_node": True,
                "exercise_chapter_no": index,
            }
        )

    if not children:
        return []

    return [
        {
            "node_id": "exercise_root",
            "parent_id": None,
            "title": "习题",
            "level": 0,
            "path": ["习题"],
            "children": children,
            "is_exercise_node": True,
        }
    ]


def _append_exercise_tree(reading_tree: list[dict]) -> list[dict]:
    formatted = _build_restructured_reading_tree(reading_tree)
    if len(formatted) != 1:
        return formatted
    root = dict(formatted[0])
    children = list(root.get("children") or [])
    children.extend(_build_exercise_tree_for_reading(formatted))
    root["children"] = children
    return [root]


def _exercise_payload_for_node(node_id: str) -> dict | None:
    if node_id == "exercise_root":
        return {
            "node_id": node_id,
            "title": "习题",
            "path": ["习题"],
            "start_page": None,
            "images": [],
            "sections": [],
            "exercise_questions": [],
            "content_mode": "exercise_root",
        }

    match = re.fullmatch(r"exercise_chapter_(\d+)", str(node_id or ""))
    if not match:
        return None

    chapter_no = int(match.group(1))
    workbook_items = _workbook_questions_for_chapter(chapter_no)
    questions = []
    if workbook_items:
        grouped = _group_exercise_questions([_format_bank_question(item, chapter_no=chapter_no) for item in workbook_items])
        questions = [_combine_question_group(dict(item)) for item in grouped]
    return {
        "node_id": node_id,
        "title": f"{_chapter_title_defaults().get(chapter_no, f'第 {chapter_no} 章')}习题",
        "path": ["习题", f"{_chapter_title_defaults().get(chapter_no, f'第 {chapter_no} 章')}习题"],
        "start_page": None,
        "images": [],
        "sections": [],
        "exercise_questions": questions,
        "content_mode": "exercise_only",
    }


def _collect_display_descendant_ids(nodes: list[dict]) -> list[str]:
    node_ids: list[str] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        if node.get("node_id"):
            node_ids.append(node["node_id"])
        node_ids.extend(_collect_display_descendant_ids(node.get("children") or []))
    return node_ids


def _synthetic_chapter_payload(node: dict, include_children: bool = True) -> dict:
    sections_map = _get_reading_sections_map()
    target_ids = _collect_display_descendant_ids(node.get("children") or [])
    target_sections = [sections_map[node_id] for node_id in target_ids if node_id in sections_map]
    target_sections.sort(key=lambda item: (item.get("start_page") or 10**9, item.get("title") or ""))

    pages = []
    seen_page_keys = set()
    for section in target_sections:
        section_pages = section.get("combined_pages") if include_children else section.get("pages")
        if not section_pages:
            section_pages = section.get("combined_pages") or section.get("pages") or []
        for page in section_pages:
            if not isinstance(page, dict):
                continue
            page_key = (page.get("page"), page.get("text"))
            if page_key in seen_page_keys:
                continue
            seen_page_keys.add(page_key)
            pages.append(page)

    start_page = min((section.get("start_page") for section in target_sections if isinstance(section.get("start_page"), int)), default=None)
    title = _tidy_reading_text(node.get("title") or "")
    path = [_tidy_reading_text(item) for item in _normalize_path(node.get("path") or [])]
    section_images = _images_for_reading_section(title, path, pages)
    paragraphs = _attach_images_to_paragraphs(_format_reading_pages(pages, title), section_images)
    return {
        "node_id": node.get("node_id"),
        "title": title,
        "path": path,
        "start_page": start_page,
        "images": section_images,
        "sections": [
            {
                "node_id": node.get("node_id"),
                "title": title,
                "level": int(node.get("level") or 1),
                "path": path,
                "start_page": start_page,
                "images": section_images,
                "paragraphs": paragraphs,
                "content_mode": "complete_textbook",
            }
        ],
        "exercise_questions": [],
        "content_mode": "complete_textbook",
    }


def _section_payload_from_reading(node_id: str, include_children: bool = True) -> dict | None:
    exercise_payload = _exercise_payload_for_node(node_id)
    if exercise_payload is not None:
        return exercise_payload

    tree = _build_restructured_reading_tree(_get_reading_tree())
    sections_map = _get_reading_sections_map()
    node = _find_tree_node(node_id, tree) or sections_map.get(node_id)
    section = sections_map.get(node_id)
    if not node and not section:
        return None
    if isinstance(node, dict) and node.get("is_synthetic_chapter"):
        return _synthetic_chapter_payload(node, include_children)

    base = section or node or {}
    pages = base.get("combined_pages") if include_children else base.get("pages")
    if not pages:
        pages = base.get("combined_pages") or base.get("pages")

    node_title = node.get("title") if isinstance(node, dict) else ""
    node_path = node.get("path") if isinstance(node, dict) else []
    node_level = node.get("level") if isinstance(node, dict) else 0
    node_start_page = node.get("start_page") if isinstance(node, dict) else None
    title = _tidy_reading_text(base.get("title") or node_title)
    path = [_tidy_reading_text(item) for item in _normalize_path(base.get("path") or node_path)]
    start_page = base.get("combined_start_page") if include_children else base.get("start_page")
    if start_page in (None, ""):
        start_page = base.get("start_page") or node_start_page

    section_images = _images_for_reading_section(title, path, pages)
    paragraphs = _attach_images_to_paragraphs(_format_reading_pages(pages, title), section_images)

    return {
        "node_id": node_id,
        "title": title,
        "path": path,
        "start_page": start_page,
        "images": section_images,
        "sections": [
            {
                "node_id": node_id,
                "title": title,
                "level": int(base.get("level") or node_level or 0),
                "path": path,
                "start_page": start_page,
                "images": section_images,
                "paragraphs": paragraphs,
                "content_mode": "complete_textbook",
            }
        ],
        "exercise_questions": [],
        "content_mode": "complete_textbook",
    }


def get_course_name() -> str:
    reading_content = get_reading_content()
    if isinstance(reading_content, dict):
        for key in ("course_name", "course", "title", "name"):
            value = reading_content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    chapter_index = get_chapter_index()
    if isinstance(chapter_index, dict):
        for key in ("course_name", "course", "title", "name"):
            value = chapter_index.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    tree = get_knowledge_tree()
    if isinstance(tree, dict):
        for key in ("course_name", "title", "name"):
            value = tree.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "软件工程"


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]+", "", _clean_text(text).lower())


def _normalize_path(value) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        text = _clean_text(value)
        if not text:
            return []
        if " / " in text:
            return [_clean_text(item) for item in text.split(" / ") if _clean_text(item)]
        parts = re.split(r"[>/|]+", text)
        return [_clean_text(item) for item in parts if _clean_text(item)]
    return []


def _format_size(size: int) -> str:
    if not size:
        return "0B"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{int(size)}B"


def _score_to_percent(score, mode: str) -> float:
    try:
        value = float(score)
    except Exception:
        return 0.0
    if mode == "vector":
        return round(max(0.0, min(1.0, 1.0 / (1.0 + max(value, 0.0)))), 4)
    return round(max(0.0, min(1.0, value / 100.0 if value > 1 else value)), 4)


def _clean_paragraph_text(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    compact = cleaned.replace(" ", "")
    if re.fullmatch(r"(?:\u7b2c)?\d+(?:\u9875)?", compact):
        return ""
    if re.fullmatch(r"[-_=.~路]{3,}", cleaned):
        return ""
    if len(compact) <= 1:
        return ""
    if re.fullmatch(r"\u7b2c[0-9\u4e00-\u9fa5]+\u7ae0.{0,24}", compact):
        return ""
    return cleaned


def _resolve_json_path(json_path: str) -> Path:
    raw = _clean_text(json_path)
    if not raw:
        raise ValueError("缺少教材 JSON 路径")
    candidates = [
        Path(raw),
        PROJECT_ROOT / raw,
        PROJECT_ROOT / "rag_data" / "pdf_json" / raw,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("教材 JSON 文件不存在")


def _default_book_json_path() -> str:
    pdf_dir = PROJECT_ROOT / "rag_data" / "pdf_json"
    if not pdf_dir.exists():
        return ""
    files = sorted(pdf_dir.glob("*.json"))
    return str(files[0].resolve()) if files else ""


def get_descendant_sections(node_id: str, rows: list[dict] | None = None) -> list[dict]:
    """递归查询当前章节及所有子章节，按原始章节顺序排列。"""
    sections = rows if rows is not None else _query_sections()
    return _get_descendant_sections(node_id, sections)


def _load_book_from_path(json_path: str):
    path = _resolve_json_path(json_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"教材 JSON 格式错误：{exc}")
    return data, path.name, str(path.resolve()), path.stat().st_size


def _load_book_payload(payload: dict):
    upload = request.files.get("file")
    if upload:
        try:
            raw = upload.read()
            data = json.loads(raw.decode("utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError("教材 JSON 文件不存在")
        except json.JSONDecodeError as exc:
            raise ValueError(f"教材 JSON 格式错误：{exc}")
        source_path = Path(upload.filename or "uploaded_book.json")
        return data, source_path.name, str(source_path.resolve()), len(raw)

    json_path = _clean_text(payload.get("json_path"))
    if not json_path:
        raise ValueError("缺少教材 JSON 路径")
    return _load_book_from_path(json_path)


def _validate_book_payload(data: dict) -> tuple[str, str, list[dict]]:
    if not isinstance(data, dict):
        raise ValueError("教材 JSON 顶层必须是对象")
    course = _clean_text(data.get("course")) or "未命名课程"
    source_file = _clean_text(data.get("source_file")) or "unknown.json"
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("教材 JSON 中 sections 为空")
    return course, source_file, sections


def _delete_existing_book(course: str, file_name: str, file_path: str, source_file: str) -> None:
    mysql_db.delete("knowledge_chunks", "course=%s AND source_file=%s", (course, source_file))
    mysql_db.delete("knowledge_sections", "course=%s AND source_file=%s", (course, source_file))
    docs = mysql_db.query_all(
        """
        SELECT id FROM knowledge_documents
        WHERE course=%s AND (file_name=%s OR file_path=%s OR file_name=%s)
        """,
        (course, file_name, file_path, source_file),
    )
    for row in docs:
        doc_id = row["id"]
        mysql_db.delete("knowledge_chunks", "document_id=%s", (doc_id,))
        mysql_db.delete("knowledge_sections", "document_id=%s", (doc_id,))
        mysql_db.delete("knowledge_documents", "id=%s", (doc_id,))


def _import_book_rows(data: dict, file_name: str, file_path: str, file_size: int) -> dict:
    course, source_file, sections = _validate_book_payload(data)
    _delete_existing_book(course, file_name, file_path, source_file)

    document_id = mysql_db.insert(
        "knowledge_documents",
        {
            "file_name": file_name,
            "file_path": file_path,
            "course": course,
            "type": "JSON",
            "size": file_size,
            "section_count": 0,
            "chunk_count": 0,
            "status": "imported",
        },
    )

    section_count = 0
    chunk_count = 0

    for sort_order, raw_section in enumerate(sections):
        if not isinstance(raw_section, dict):
            continue

        node_id = _clean_text(raw_section.get("node_id")) or f"{source_file}::{sort_order}"
        parent_id = _clean_text(raw_section.get("parent_id")) or None
        title = _clean_text(raw_section.get("title")) or f"Untitled Section {sort_order + 1}"
        level = int(raw_section.get("level") or 0)
        chapter_id = _clean_text(raw_section.get("chapter_id")) or None
        start_page = raw_section.get("start_page")
        try:
            start_page = int(start_page) if start_page not in (None, "") else None
        except Exception:
            start_page = None
        path = _normalize_path(raw_section.get("path") or [course, title])

        section_id = mysql_db.insert(
            "knowledge_sections",
            {
                "document_id": document_id,
                "node_id": node_id,
                "parent_id": parent_id,
                "title": title,
                "level": level,
                "chapter_id": chapter_id,
                "start_page": start_page,
                "path_json": _json_dumps(path),
                "path_text": " / ".join(path),
                "course": course,
                "source_file": source_file,
                "sort_order": sort_order,
            },
        )
        section_count += 1

        for chunk_index, raw_paragraph in enumerate(raw_section.get("paragraphs") or []):
            if not isinstance(raw_paragraph, dict):
                continue
            content = _clean_paragraph_text(raw_paragraph.get("text"))
            if not content:
                continue
            page = raw_paragraph.get("page")
            page_text = str(page).strip() if page not in (None, "") else ""
            mysql_db.insert(
                "knowledge_chunks",
                {
                    "document_id": document_id,
                    "section_id": section_id,
                    "section_node_id": node_id,
                    "chapter_id": chapter_id,
                    "section_title": title,
                    "path_json": _json_dumps(path),
                    "path_text": " / ".join(path),
                    "page": page_text,
                    "content": content,
                    "chunk_index": chunk_index,
                    "course": course,
                    "source_file": source_file,
                    "embedding_id": None,
                },
            )
            chunk_count += 1

    mysql_db.update(
        "knowledge_documents",
        {
            "section_count": section_count,
            "chunk_count": chunk_count,
            "status": "built" if chunk_count > 0 else "imported",
        },
        "id=%s",
        (document_id,),
    )
    return {
        "document_id": document_id,
        "course": course,
        "source_file": source_file,
        "document_count": 1,
        "section_count": section_count,
        "chunk_count": chunk_count,
    }


def _format_document_status(status: str) -> str:
    return DOCUMENT_STATUS_MAP.get(_clean_text(status), "已导入")


def _query_documents() -> list[dict]:
    rows = mysql_db.query_all(
        """
        SELECT id, file_name, file_path, course, type, size, section_count, chunk_count, status, created_at, updated_at
        FROM knowledge_documents
        ORDER BY updated_at DESC, id DESC
        """
    )
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "file_name": row["file_name"],
                "file_path": row.get("file_path") or "",
                "course": row["course"],
                "type": row["type"],
                "size": _format_size(int(row.get("size") or 0)),
                "section_count": int(row.get("section_count") or 0),
                "chunk_count": int(row.get("chunk_count") or 0),
                "status": _format_document_status(row.get("status") or "imported"),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return result


def _query_sections(document_id=None) -> list[dict]:
    sql = """
    SELECT id, document_id, node_id, parent_id, title, level, chapter_id, start_page, path_json, path_text, course, source_file, sort_order
    FROM knowledge_sections
    """
    params = []
    if document_id:
        sql += " WHERE document_id=%s"
        params.append(document_id)
    sql += " ORDER BY sort_order ASC, start_page ASC, id ASC"
    rows = mysql_db.query_all(sql, tuple(params))
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "document_id": row.get("document_id"),
                "node_id": row["node_id"],
                "parent_id": row.get("parent_id"),
                "title": row["title"],
                "level": int(row.get("level") or 0),
                "chapter_id": row.get("chapter_id"),
                "start_page": row.get("start_page"),
                "path": _normalize_path(_json_loads(row.get("path_json"), []) or row.get("path_text")),
                "course": row.get("course") or "",
                "source_file": row.get("source_file") or "",
                "sort_order": int(row.get("sort_order") or 0),
            }
        )
    return result


def _build_tree(rows: list[dict]) -> list[dict]:
    children_map: dict[str | None, list[dict]] = {}
    id_map = {}

    for row in rows:
        id_map[row["node_id"]] = {**row, "children": []}
        children_map.setdefault(row.get("parent_id") or None, []).append(id_map[row["node_id"]])

    def sort_nodes(nodes: list[dict]) -> list[dict]:
        return sorted(nodes, key=lambda item: (item.get("sort_order", 0), item.get("start_page") or 10**9, item.get("title") or ""))

    def attach(node: dict) -> dict:
        node["children"] = [attach(child) for child in sort_nodes(children_map.get(node["node_id"], []))]
        return node

    roots = [row for row in rows if not row.get("parent_id") or row.get("parent_id") not in id_map]
    return [attach(id_map[row["node_id"]]) for row in sort_nodes(roots)]


def _get_descendant_sections(node_id: str, rows: list[dict]) -> list[dict]:
    id_map = {row["node_id"]: row for row in rows}
    children_map: dict[str, list[dict]] = {}
    for row in rows:
        parent_id = row.get("parent_id")
        if parent_id:
            children_map.setdefault(parent_id, []).append(row)
    for key in children_map:
        children_map[key] = sorted(children_map[key], key=lambda item: (item.get("sort_order", 0), item.get("start_page") or 10**9, item.get("title") or ""))

    result = []

    def dfs(current_id: str):
        node = id_map.get(current_id)
        if not node:
            return
        result.append(node)
        for child in children_map.get(current_id, []):
            dfs(child["node_id"])

    dfs(node_id)
    return result


def _query_chunks_by_section_nodes(node_ids: list[str]) -> list[dict]:
    if not node_ids:
        return []
    placeholders = ", ".join(["%s"] * len(node_ids))
    sql = f"""
    SELECT section_node_id, section_title, path_json, path_text, page, content, chunk_index
    FROM knowledge_chunks
    WHERE section_node_id IN ({placeholders})
    ORDER BY id ASC
    """
    rows = mysql_db.query_all(sql, tuple(node_ids))
    result = []
    for row in rows:
        result.append(
            {
                "section_node_id": row["section_node_id"],
                "section_title": row.get("section_title") or "",
                "path": _normalize_path(_json_loads(row.get("path_json"), []) or row.get("path_text")),
                "page": row.get("page"),
                "content": row.get("content") or "",
                "chunk_index": int(row.get("chunk_index") or 0),
            }
        )
    def page_sort_value(value):
        text = _clean_text(value)
        digits = re.findall(r"\d+", text)
        if digits:
            try:
                return int(digits[0])
            except Exception:
                return 10**9
        return 10**9
    return sorted(result, key=lambda item: (page_sort_value(item.get("page")), item.get("chunk_index", 0)))


def _extract_search_tokens(query: str) -> list[str]:
    text = _clean_text(query)
    if not text:
        return []
    scrubbed = text
    for stop in ("是什么", "为什么", "如何", "怎么", "哪些", "什么原因", "什么", "吗", "呢", "的", "了"):
        scrubbed = scrubbed.replace(stop, " ")
    scrubbed = re.sub(r"[？?。，,；;！!、]", " ", scrubbed)
    tokens: list[str] = []
    for part in re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}", scrubbed):
        tokens.append(part)
    for segment in re.findall(r"[\u4e00-\u9fa5]+", text):
        normalized = _normalize_text(segment)
        if len(normalized) < 2:
            continue
        for size in range(min(6, len(normalized)), 1, -1):
            for index in range(len(normalized) - size + 1):
                gram = normalized[index : index + size]
                if len(gram) >= 2 and gram not in tokens:
                    tokens.append(gram)
    return list(dict.fromkeys(tokens))[:50]


def _database_keyword_search(query: str, top_k: int) -> list[dict]:
    text = _clean_text(query)
    if not text:
        return []
    tokens = _extract_search_tokens(text)
    rows = mysql_db.query_all(
        """
        SELECT section_title, path_text, page, content
        FROM knowledge_chunks
        ORDER BY id DESC
        LIMIT 5000
        """
    )
    scored = []
    compact_query = _normalize_text(text)
    for index, row in enumerate(rows):
        content = row.get("content") or ""
        section_title = row.get("section_title") or ""
        path_text = row.get("path_text") or ""
        compact_content = _normalize_text(content)
        compact_title = _normalize_text(section_title)
        compact_path = _normalize_text(path_text)

        score = 0.0
        if compact_query and compact_query in compact_content:
            score += 80
        if compact_query and compact_query in compact_title:
            score += 40
        if compact_query and compact_query in compact_path:
            score += 20

        matched_tokens = 0
        for token in tokens:
            token_norm = _normalize_text(token)
            if not token_norm:
                continue
            weight = min(len(token_norm), 8)
            token_hit = False
            if token_norm in compact_title:
                score += 10 + weight
                token_hit = True
            if token_norm in compact_path:
                score += 6 + weight // 2
                token_hit = True
            if token_norm in compact_content:
                score += 4 + weight
                token_hit = True
            if token_hit:
                matched_tokens += 1

        if score <= 0:
            continue
        if len(tokens) >= 2 and matched_tokens < 1:
            continue

        scored.append(
            (
                score,
                matched_tokens,
                -index,
                {
                    "content": content[:300],
                    "section_title": section_title,
                    "path": path_text,
                    "page": row.get("page"),
                    "score": round(min(0.9999, score / 100.0), 4),
                },
            )
        )

    scored.sort(reverse=True)
    return [item[3] for item in scored[:top_k]]


def bootstrap_knowledge_base() -> dict | None:
    """首次启动时，如果知识库为空则自动导入默认教材 JSON。"""
    try:
        docs = _query_documents()
        if docs:
            return None
        json_path = _default_book_json_path()
        if not json_path:
            return None
        data, file_name, file_path, file_size = _load_book_from_path(json_path)
        return _import_book_rows(data, file_name, file_path, file_size)
    except Exception:
        return None


def _vector_search(query: str, top_k: int) -> list[dict]:
    results = []
    for item in retrieve_knowledge_items(query, top_k=top_k):
        metadata = item.get("metadata") or {}
        path = metadata.get("section_path") or []
        pages = metadata.get("pages") or []
        results.append(
            {
                "content": _clean_text(item.get("content"))[:300],
                "section_title": metadata.get("section_title") or (path[-1] if path else metadata.get("title") or "Unknown Section"),
                "path": " / ".join(path),
                "page": pages[0] if pages else "",
                "score": _score_to_percent(item.get("score"), item.get("retrieval_mode") or "vector"),
            }
        )
    return results


def _search_knowledge(query: str, top_k: int) -> list[dict]:
    db_items = _database_keyword_search(query, top_k)
    if db_items:
        return db_items
    return _vector_search(query, top_k)


def candidate_image_paths(raw_path: str) -> list[Path]:
    kb_root = generated_kb_dir().resolve()
    image_root = (kb_root / "images").resolve()
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
        candidates.append(image_root / normalized.split(marker, 1)[1])

    if not raw_candidate.is_absolute():
        candidates.append(image_root / raw_path)

    unique = []
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


def resolve_image_path(raw_path: str) -> Path | None:
    image_root = (generated_kb_dir() / "images").resolve()
    for image_path in candidate_image_paths(raw_path):
        if image_path.exists() and image_path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            if image_path == image_root or image_root in image_path.parents:
                return image_path
    return None


@knowledge_bp.post("/import-book-json")
@login_required
def import_book_json():
    try:
        payload = request.get_json(silent=True) or {}
        data, file_name, file_path, file_size = _load_book_payload(payload)
        imported = _import_book_rows(data, file_name, file_path, file_size)
        try:
            build_vector_db(force=True)
        except Exception:
            pass
        return success(imported, "教材 JSON 导入成功")
    except FileNotFoundError as exc:
        return fail(str(exc), 400)
    except ValueError as exc:
        return fail(str(exc), 400)
    except Exception as exc:
        return fail(f"知识库导入失败：{exc}", 500)


@knowledge_bp.get("/status")
@login_required
def status():
    try:
        docs = _query_documents()
        section_total = sum(int(item.get("section_count") or 0) for item in docs)
        chunk_total = sum(int(item.get("chunk_count") or 0) for item in docs)

        legacy_status = rag_status()
        reading_sections = _get_reading_sections_map()
        if reading_sections and not section_total:
            section_total = len(reading_sections)
        mode = legacy_status.get("retrieval_mode") or legacy_status.get("last_build", {}).get("retrieval_mode") or "keyword"
        search_mode = "向量" if str(mode).lower() == "vector" else "关键词"
        course_name = docs[0]["course"] if docs else legacy_status.get("course_name") or get_course_name()
        document_count = len(docs) or (1 if reading_sections else 0)
        built = chunk_total > 0 or bool(reading_sections)
        return success(
            {
                "course_name": course_name,
                "document_count": document_count,
                "section_count": section_total,
                "chunk_count": chunk_total,
                "search_mode": search_mode,
                "built": built,
                "status_text": "知识库已构建" if built else "知识库尚未构建",
                "default_json_path": _default_book_json_path(),
            },
            "知识库状态加载成功",
        )
    except Exception as exc:
        return fail(f"知识库状态获取失败：{exc}", 500)


@knowledge_bp.get("/documents")
@login_required
def documents():
    try:
        return success(_query_documents(), "文档列表加载成功")
    except Exception as exc:
        return fail(f"文档列表获取失败：{exc}", 500)


@knowledge_bp.post("/rebuild")
@login_required
def rebuild():
    try:
        payload = request.get_json(silent=True) or {}
        json_path = _clean_text(payload.get("json_path"))
        if not json_path:
            latest = mysql_db.query_one("SELECT file_path FROM knowledge_documents ORDER BY updated_at DESC, id DESC LIMIT 1")
            json_path = _clean_text((latest or {}).get("file_path"))
        if not json_path:
            json_path = _default_book_json_path()
        if not json_path:
            return fail("没有可用的教材 JSON 路径，请先导入教材", 400)
        data, file_name, file_path, file_size = _load_book_payload({"json_path": json_path})
        imported = _import_book_rows(data, file_name, file_path, file_size)
        vector_status = "skipped"
        try:
            build_vector_db(force=True)
            vector_status = "rebuilt"
        except Exception:
            vector_status = "unavailable"
        imported["vector_status"] = vector_status
        return success(imported, "知识库重建完成")
    except FileNotFoundError as exc:
        return fail(str(exc), 400)
    except ValueError as exc:
        return fail(str(exc), 400)
    except Exception as exc:
        return fail(f"知识库重建失败：{exc}", 500)


@knowledge_bp.post("/search")
@login_required
def search():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["query"])
        if not ok:
            return fail(f"缺少必填字段：{field}", 400)
        query = _clean_text(payload.get("query"))
        if not query:
            return fail("请输入检索内容", 400)
        top_k = int(payload.get("top_k", 5) or 5)
        items = _search_knowledge(query, top_k)
        if not items:
            return success([], "未检索到相关内容")
        return success(items, "检索完成")
    except Exception as exc:
        return fail(f"知识库检索失败：{exc}", 500)


@knowledge_bp.get("/chapter-index")
@login_required
def chapter_index():
    try:
        return success(get_chapter_index(), "Chapter index loaded")
    except Exception as exc:
        return fail(f"Chapter index failed: {exc}", 500)


@knowledge_bp.get("/chapter-browser")
@login_required
def chapter_browser():
    try:
        reading_tree = _get_reading_tree()
        if reading_tree:
            return success({"course_name": get_course_name(), "tree": _append_exercise_tree(reading_tree)}, "Chapter browser loaded")
        sections = _query_sections()
        if sections:
            return success({"course_name": get_course_name(), "tree": _build_tree(sections)}, "Chapter browser loaded")
        return success(get_chapter_index(), "Chapter browser loaded")
    except Exception as exc:
        return fail(f"Chapter browser failed: {exc}", 500)


@knowledge_bp.get("/tree")
@login_required
def tree():
    try:
        reading_tree = _get_reading_tree()
        if reading_tree:
            return success(_append_exercise_tree(reading_tree), "Tree loaded")
        sections = _query_sections()
        return success(_build_tree(sections), "Tree loaded")
    except Exception as exc:
        return fail(f"Tree load failed: {exc}", 500)


@knowledge_bp.get("/section/<node_id>")
@login_required
def section_detail(node_id: str):
    try:
        include_children = str(request.args.get("include_children", "true")).lower() == "true"
        reading_payload = _section_payload_from_reading(node_id, include_children)
        if reading_payload:
            return success(reading_payload, "章节内容加载成功")

        sections = _query_sections()
        node = next((item for item in sections if item["node_id"] == node_id), None)
        if not node:
            return fail("章节不存在", 404)

        target_sections = get_descendant_sections(node_id, sections) if include_children else [node]
        chunks = _query_chunks_by_section_nodes([item["node_id"] for item in target_sections])
        chunk_map: dict[str, list[dict]] = {}
        for chunk in chunks:
            chunk_map.setdefault(chunk["section_node_id"], []).append({"page": chunk.get("page"), "text": chunk.get("content") or ""})

        ordered_sections = []
        for item in target_sections:
            ordered_sections.append(
                {
                    "node_id": item["node_id"],
                    "title": item["title"],
                    "level": item["level"],
                    "path": item["path"],
                    "start_page": item.get("start_page"),
                    "paragraphs": chunk_map.get(item["node_id"], []),
                }
            )

        return success(
            {
                "node_id": node["node_id"],
                "title": node["title"],
                "path": node["path"],
                "start_page": node.get("start_page"),
                "sections": ordered_sections,
            },
            "章节内容加载成功",
        )
    except Exception as exc:
        return fail(f"章节内容加载失败：{exc}", 500)


@knowledge_bp.get("/knowledge-tree")
@login_required
def knowledge_tree():
    try:
        return success(get_knowledge_tree(), "Knowledge tree loaded")
    except Exception as exc:
        return fail(f"Knowledge tree failed: {exc}", 500)


@knowledge_bp.get("/knowledge-graph")
@login_required
def knowledge_graph():
    try:
        return success(get_detailed_knowledge_tree(), "Knowledge graph loaded")
    except Exception as exc:
        return fail(f"Knowledge graph failed: {exc}", 500)


@knowledge_bp.get("/image")
def image():
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        return fail("Missing image path", 400)
    try:
        image_path = resolve_image_path(raw_path)
        if not image_path:
            return fail("Image not found or unsupported", 404)
        return send_file(str(image_path))
    except Exception as exc:
        return fail(f"Image read failed: {exc}", 500)


def candidate_video_paths(raw_path: str) -> list[Path]:
    kb_root = generated_kb_dir().resolve()
    video_root = (kb_root / "videos").resolve()
    normalized = raw_path.strip().strip('"').strip("'").replace("\\", "/")
    candidates: list[Path] = []
    raw_candidate = Path(raw_path)
    if raw_candidate.is_absolute():
        candidates.append(raw_candidate)
    if normalized.startswith("videos/"):
        candidates.append(kb_root / normalized)
        candidates.append(video_root / normalized[len("videos/") :])
    marker = "/videos/"
    if marker in normalized:
        candidates.append(video_root / normalized.split(marker, 1)[1])
    if not raw_candidate.is_absolute():
        candidates.append(video_root / raw_path)
    unique = []
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


def resolve_video_path(raw_path: str) -> Path | None:
    video_root = (generated_kb_dir() / "videos").resolve()
    for video_path in candidate_video_paths(raw_path):
        if video_path.exists() and video_path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
            if video_path == video_root or video_root in video_path.parents:
                return video_path
    return None


@knowledge_bp.get("/video")
def video():
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        return fail("Missing video path", 400)
    try:
        video_path = resolve_video_path(raw_path)
        if not video_path:
            return fail("Video not found or unsupported", 404)
        return send_file(str(video_path), conditional=True)
    except Exception as exc:
        return fail(f"Video read failed: {exc}", 500)
