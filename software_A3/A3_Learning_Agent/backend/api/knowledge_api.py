import json
import re
from pathlib import Path

from flask import Blueprint, request, send_file

from config import config
from db import mysql_db
from ai.rag import build_vector_db, rag_status, retrieve_knowledge_items
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

knowledge_bp = Blueprint("knowledge", __name__)
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
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


def _load_first_json(folder_name: str, default):
    folder = _json_dir(folder_name)
    for file_path in _iter_json_files(folder):
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
                paragraphs.append({"text": text})
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


def _section_payload_from_reading(node_id: str, include_children: bool = True) -> dict | None:
    tree = _get_reading_tree()
    sections_map = _get_reading_sections_map()
    node = _find_tree_node(node_id, tree) or sections_map.get(node_id)
    section = sections_map.get(node_id)
    if not node and not section:
        return None

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

    return {
        "node_id": node_id,
        "title": title,
        "path": path,
        "start_page": start_page,
        "sections": [
            {
                "node_id": node_id,
                "title": title,
                "level": int(base.get("level") or node_level or 0),
                "path": path,
                "start_page": start_page,
                "paragraphs": _format_reading_pages(pages, title),
                "content_mode": "complete_textbook",
            }
        ],
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
            return success({"course_name": get_course_name(), "tree": _format_reading_tree_nodes(reading_tree)}, "Chapter browser loaded")
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
            return success(_format_reading_tree_nodes(reading_tree), "Tree loaded")
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
