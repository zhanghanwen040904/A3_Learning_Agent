import json
import re
import shutil
from pathlib import Path
from typing import Iterable, List

try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None
    Settings = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

from config import config

_COLLECTION_NAME = "software_engineering_course"
_embedding_model = None
_chroma_client = None
_collection = None
_fallback_chunks: List[dict] = []
_last_build_result = {"status": "not_built", "chunks": 0, "message": "知识库尚未构建"}

FORBIDDEN_FRONTEND_FIELDS = {
    "debug",
    "generation_rules",
    "images",
    "knowledge_base_dir",
    "knowledge_tree",
    "prompt",
    "query",
    "raw_request",
    "raw_response",
    "retrieved_chunks",
    "system_prompt",
    "user_prompt",
}


def generated_kb_dir() -> Path:
    return Path(config.RAG_SOURCE_DIR).parent


def _json_dir(name: str) -> Path:
    return generated_kb_dir() / name


def student_knowledge_base_dir() -> Path:
    return _json_dir("student_knowledge_base_json")


def chapter_index_dir() -> Path:
    return _json_dir("chapter_index_json")


def knowledge_points_dir() -> Path:
    return _json_dir("knowledge_points_json")


def textbook_knowledge_dir() -> Path:
    return _json_dir("textbook_knowledge_json")


def questions_json_dir() -> Path:
    return _json_dir("questions_json")


def knowledge_tree_dir() -> Path:
    return _json_dir("knowledge_tree_json")


def detailed_knowledge_tree_dir() -> Path:
    return _json_dir("detailed_knowledge_tree_json")


def semantic_json_dir() -> Path:
    return _json_dir("semantic_json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_json_files(folder: Path) -> Iterable[Path]:
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"))


def clean_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_string(value: str) -> str:
    text = clean_text(value).lower()
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("，", ",").replace("：", ":").replace("；", ";")
    text = re.sub(r"[^\u4e00-\u9fa5a-z0-9]+", "", text)
    return text


def _tokenize_query(query: str) -> List[str]:
    text = clean_text(query)
    words = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}", text)
    return list(dict.fromkeys(words))


def _pages_text(pages) -> str:
    if isinstance(pages, list):
        return ",".join(str(item) for item in pages if str(item).strip())
    return str(pages or "")


def _safe_learning_location(item: dict) -> dict:
    location = item.get("learning_location") or {}
    if isinstance(location, dict) and any(location.values()):
        return {
            "unit": location.get("unit") or "",
            "chapter": location.get("chapter") or "",
            "section": location.get("section") or "",
            "subsection": location.get("subsection") or "",
            "path": location.get("path") or item.get("section_path") or [],
            "path_text": location.get("path_text") or " / ".join(item.get("section_path") or []),
            "pages": location.get("pages") or item.get("pages") or [],
        }
    section_path = item.get("section_path") or []
    if not isinstance(section_path, list):
        section_path = [str(section_path)] if section_path else []
    return {
        "unit": section_path[0] if len(section_path) > 0 else "",
        "chapter": section_path[1] if len(section_path) > 1 else "",
        "section": section_path[2] if len(section_path) > 2 else "",
        "subsection": section_path[3] if len(section_path) > 3 else "",
        "path": section_path,
        "path_text": " / ".join(section_path),
        "pages": item.get("pages") or [],
    }


def _safe_student_item(item: dict, retrieval_source: str) -> dict:
    return {
        "knowledge_id": item.get("knowledge_id") or item.get("chunk_id") or "",
        "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or "",
        "title": clean_text(item.get("title") or ""),
        "normalized_title": clean_text(item.get("normalized_title") or item.get("title") or ""),
        "content": clean_text(item.get("content") or ""),
        "content_preview": clean_text(item.get("content_preview") or item.get("content") or "")[:220],
        "section_path": item.get("section_path") or [],
        "learning_location": _safe_learning_location(item),
        "pages": item.get("pages") or [],
        "source_file": item.get("source_file") or "",
        "knowledge_type": item.get("knowledge_type") or "",
        "knowledge_level": item.get("knowledge_level") or "",
        "is_primary_knowledge": bool(item.get("is_primary_knowledge")),
        "tags": item.get("tags") or [],
        "parent_titles": item.get("parent_titles") or [],
        "child_titles": item.get("child_titles") or [],
        "related_knowledge_titles": item.get("related_knowledge_titles") or [],
        "retrieval_source": retrieval_source,
    }


def _load_student_knowledge_items() -> List[dict]:
    items: List[dict] = []
    for path in _iter_json_files(student_knowledge_base_dir()):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        source_file = payload.get("source_file") or path.name
        for row in payload.get("knowledge_points") or []:
            item = _safe_student_item({**row, "source_file": row.get("source_file") or source_file}, "student_knowledge_base_json")
            if item["title"] and item["content"]:
                items.append(item)
    return items


def _load_knowledge_points_items() -> List[dict]:
    items: List[dict] = []
    for path in _iter_json_files(knowledge_points_dir()):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        rows = payload.get("knowledge_points") or payload.get("items") or payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = _safe_student_item(
                {
                    "knowledge_id": row.get("knowledge_id") or row.get("node_id") or row.get("chunk_id"),
                    "chunk_id": row.get("chunk_id") or row.get("knowledge_id") or row.get("node_id"),
                    "title": row.get("title"),
                    "content": row.get("content") or row.get("description") or row.get("source_text"),
                    "content_preview": row.get("content_preview") or row.get("content") or row.get("description"),
                    "section_path": row.get("section_path") or [],
                    "learning_location": row.get("learning_location") or {},
                    "pages": row.get("pages") or [],
                    "source_file": row.get("source_file") or path.name,
                    "knowledge_type": row.get("knowledge_type") or row.get("node_type") or "",
                    "tags": row.get("tags") or [],
                    "related_knowledge_titles": row.get("related_knowledge_titles") or [],
                },
                "knowledge_points_json",
            )
            if item["title"] and item["content"]:
                items.append(item)
    return items


def _load_textbook_knowledge_items() -> List[dict]:
    items: List[dict] = []
    for path in _iter_json_files(textbook_knowledge_dir()):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        rows = payload.get("knowledge_points") or payload.get("items") or payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = _safe_student_item(
                {
                    "knowledge_id": row.get("knowledge_id") or row.get("chunk_id"),
                    "chunk_id": row.get("chunk_id") or row.get("knowledge_id"),
                    "title": row.get("title"),
                    "content": row.get("content"),
                    "content_preview": row.get("content_preview") or row.get("content"),
                    "section_path": row.get("section_path") or [],
                    "learning_location": row.get("learning_location") or {},
                    "pages": row.get("pages") or [],
                    "source_file": row.get("source_file") or path.name,
                    "knowledge_type": row.get("knowledge_type") or "",
                    "tags": row.get("tags") or [],
                    "related_knowledge_titles": row.get("related_knowledge_titles") or [],
                },
                "textbook_knowledge_json",
            )
            if item["title"] and item["content"]:
                items.append(item)
    return items


def _load_chapter_index() -> dict:
    for path in _iter_json_files(chapter_index_dir()):
        try:
            return _read_json(path)
        except Exception:
            continue
    return {}


def _load_question_items() -> List[dict]:
    items: List[dict] = []
    for path in _iter_json_files(questions_json_dir()):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        rows = payload.get("questions") or payload.get("items") or payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "question_id": row.get("question_id") or "",
                    "stem": clean_text(row.get("stem") or row.get("content") or row.get("question") or ""),
                    "content": clean_text(row.get("content") or row.get("question") or ""),
                    "options": row.get("options") or [],
                    "question_type": row.get("question_type") or row.get("type") or "",
                    "section_path": row.get("section_path") or [],
                    "pages": row.get("pages") or [],
                    "related_knowledge_titles": row.get("related_knowledge_titles") or row.get("knowledge_points") or [],
                    "primary_knowledge_titles": row.get("primary_knowledge_titles") or row.get("related_knowledge_titles") or [],
                    "prerequisite_knowledge_titles": row.get("prerequisite_knowledge_titles") or [],
                    "confidence": row.get("confidence") or 0,
                    "requires_image": bool(row.get("requires_image")),
                }
            )
    return items


def list_source_documents() -> List[dict]:
    source_dir = Path(config.RAG_SOURCE_DIR)
    source_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
            documents.append(
                {
                    "name": path.name,
                    "path": str(path.relative_to(source_dir)),
                    "suffix": path.suffix.lower(),
                    "size": path.stat().st_size,
                }
            )
    return documents


def _load_semantic_chunks() -> List[dict]:
    chunks: List[dict] = []
    for index, item in enumerate(_load_student_knowledge_items()):
        chunks.append(
            {
                "source": Path(item.get("source_file") or "student_knowledge_base_json").name,
                "chunk_index": index,
                "content": item["content"],
                "doc_index": 0,
                "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"student_{index}",
                "metadata": {
                    "title": item["title"],
                    "source": item.get("source_file") or "",
                    "section_title": item.get("section_path", [""])[-1] if item.get("section_path") else "",
                    "section_path": " > ".join(item.get("section_path") or []),
                    "pages": item.get("pages") or [],
                    "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"student_{index}",
                    "knowledge_point": item["title"],
                    "knowledge_type": item.get("knowledge_type") or "",
                    "tags": item.get("tags") or [],
                    "learning_location": item.get("learning_location") or {},
                    "content_preview": item.get("content_preview") or "",
                    "related_knowledge_titles": item.get("related_knowledge_titles") or [],
                    "retrieval_source": item.get("retrieval_source") or "student_knowledge_base_json",
                },
            }
        )
    return chunks


def preprocess_text(text: str) -> str:
    return clean_text(text)


def reset_rag_cache() -> None:
    global _chroma_client, _collection
    _collection = None
    _chroma_client = None


def _get_embedding_model():
    global _embedding_model
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers 未安装，已切换为关键词检索模式")
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.RAG_EMBEDDING_MODEL)
    return _embedding_model


def _get_collection():
    global _chroma_client, _collection
    if chromadb is None or Settings is None:
        raise RuntimeError("chromadb 未安装，已切换为关键词检索模式")
    if _collection is None:
        vector_dir = Path(config.RAG_VECTOR_DIR)
        vector_dir.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(vector_dir), settings=Settings(anonymized_telemetry=False))
        _collection = _chroma_client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _build_fallback_chunks() -> List[dict]:
    chunks = _load_semantic_chunks()
    if chunks:
        return chunks
    chunks = []
    combined = _load_student_knowledge_items() or _load_knowledge_points_items() or _load_textbook_knowledge_items()
    for index, item in enumerate(combined):
        chunks.append(
            {
                "source": Path(item.get("source_file") or "knowledge").name,
                "chunk_index": index,
                "content": item["content"],
                "doc_index": 0,
                "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"fallback_{index}",
                "metadata": {
                    "title": item["title"],
                    "source": item.get("source_file") or "",
                    "section_title": item.get("section_path", [""])[-1] if item.get("section_path") else "",
                    "section_path": " > ".join(item.get("section_path") or []),
                    "pages": item.get("pages") or [],
                    "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"fallback_{index}",
                    "knowledge_point": item["title"],
                    "knowledge_type": item.get("knowledge_type") or "",
                    "tags": item.get("tags") or [],
                    "learning_location": item.get("learning_location") or {},
                    "content_preview": item.get("content_preview") or "",
                    "related_knowledge_titles": item.get("related_knowledge_titles") or [],
                    "retrieval_source": item.get("retrieval_source") or "student_knowledge_base_json",
                },
            }
        )
    return chunks


def build_vector_db(force: bool = False) -> dict:
    global _fallback_chunks, _last_build_result
    _fallback_chunks = _build_fallback_chunks()
    if not _fallback_chunks:
        _last_build_result = {"status": "empty", "documents": 0, "chunks": 0, "message": "没有可构建的课程知识数据"}
        return _last_build_result

    if force:
        reset_rag_cache()
        vector_dir = Path(config.RAG_VECTOR_DIR)
        if vector_dir.exists():
            try:
                shutil.rmtree(vector_dir)
            except Exception:
                pass

    try:
        collection = _get_collection()
        existing_count = collection.count()
        if existing_count > 0 and not force:
            if existing_count == len(_fallback_chunks):
                _last_build_result = {
                    "status": "loaded",
                    "chunks": existing_count,
                    "fallback_chunks": len(_fallback_chunks),
                    "retrieval_source": _fallback_chunks[0].get("metadata", {}).get("retrieval_source", "unknown"),
                    "message": "向量库已存在且与当前知识库数量一致，直接加载",
                }
                return _last_build_result
            try:
                collection.delete(ids=collection.get(include=[]) ["ids"])
            except Exception:
                reset_rag_cache()
                vector_dir = Path(config.RAG_VECTOR_DIR)
                if vector_dir.exists():
                    shutil.rmtree(vector_dir)
                collection = _get_collection()

        ids, texts, metadatas = [], [], []
        for item in _fallback_chunks:
            ids.append(str(item.get("chunk_id") or f"chunk_{item['chunk_index']}"))
            texts.append(item["content"])
            metadatas.append(item.get("metadata", {}) | {"source": item["source"], "chunk_index": item["chunk_index"]})
        embeddings = _get_embedding_model().encode(texts, normalize_embeddings=True).tolist()
        collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        _last_build_result = {
            "status": "created",
            "documents": len(list_source_documents()),
            "chunks": len(texts),
            "fallback_chunks": len(_fallback_chunks),
            "retrieval_mode": "vector",
            "retrieval_source": _fallback_chunks[0].get("metadata", {}).get("retrieval_source", "unknown"),
            "message": "向量库构建完成",
        }
        return _last_build_result
    except Exception as exc:
        _last_build_result = {
            "status": "fallback",
            "documents": len(list_source_documents()),
            "chunks": len(_fallback_chunks),
            "fallback_chunks": len(_fallback_chunks),
            "retrieval_mode": "keyword",
            "retrieval_source": _fallback_chunks[0].get("metadata", {}).get("retrieval_source", "unknown") if _fallback_chunks else "unknown",
            "message": "向量库暂不可用，已启用关键词检索降级模式",
            "warning": str(exc),
        }
        return _last_build_result


def _score_item(query_tokens: List[str], item: dict) -> float:
    haystack = " ".join(
        [
            item.get("title") or "",
            item.get("content_preview") or "",
            item.get("content") or "",
            " ".join(item.get("section_path") or []),
            " ".join(item.get("tags") or []),
            " ".join(item.get("related_knowledge_titles") or []),
        ]
    )
    haystack_norm = _normalize_string(haystack)
    score = 0.0
    for token in query_tokens:
        token_norm = _normalize_string(token)
        if not token_norm:
            continue
        if token_norm in _normalize_string(item.get("title") or ""):
            score += 8
        if token_norm in _normalize_string(" ".join(item.get("section_path") or [])):
            score += 6
        if token_norm in _normalize_string(" ".join(item.get("tags") or [])):
            score += 4
        if token_norm in haystack_norm:
            score += 3
    return score


def _profile_terms(profile: dict | None = None, stage: dict | None = None) -> List[str]:
    profile = profile or {}
    stage = stage or {}
    values = [
        profile.get("major"),
        profile.get("course"),
        profile.get("study_goal"),
        profile.get("current_need"),
        profile.get("course_progress"),
        profile.get("weak_points"),
        profile.get("error_prone_points"),
        profile.get("challenge_scene"),
        profile.get("selected_primary_knowledge_title"),
        stage.get("stage_title"),
        stage.get("stage_goal"),
        " ".join(stage.get("stage_points") or []),
    ]
    terms = []
    for value in values:
        for token in _tokenize_query(str(value or "")):
            if token and token not in terms:
                terms.append(token)
    return terms


def _primary_bonus(item: dict) -> float:
    bonus = 0.0
    if item.get("is_primary_knowledge"):
        bonus += 8.0
    level = clean_text(item.get("knowledge_level") or "")
    if level in {"core", "primary", "important", "??", "??"}:
        bonus += 4.0
    if item.get("parent_titles") or item.get("child_titles"):
        bonus += 1.5
    return bonus


def _student_item_to_chunk(item: dict, index: int, score: float, retrieval_mode: str = "profile_keyword") -> dict:
    return {
        "source": Path(item.get("source_file") or "knowledge").name,
        "chunk_index": index,
        "content": item.get("content") or "",
        "score": round(float(score), 4),
        "retrieval_mode": retrieval_mode,
        "metadata": {
            "title": item.get("title") or "",
            "normalized_title": item.get("normalized_title") or item.get("title") or "",
            "source": item.get("source_file") or "",
            "section_title": item.get("section_path", [""])[-1] if item.get("section_path") else "",
            "section_path": item.get("section_path") or [],
            "pages": item.get("pages") or [],
            "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"profile_{index}",
            "knowledge_point": item.get("title") or "",
            "knowledge_type": item.get("knowledge_type") or "",
            "knowledge_level": item.get("knowledge_level") or "",
            "is_primary_knowledge": bool(item.get("is_primary_knowledge")),
            "tags": item.get("tags") or [],
            "parent_titles": item.get("parent_titles") or [],
            "child_titles": item.get("child_titles") or [],
            "learning_location": item.get("learning_location") or {},
            "content_preview": item.get("content_preview") or "",
            "related_knowledge_titles": item.get("related_knowledge_titles") or [],
            "retrieval_source": item.get("retrieval_source") or "student_knowledge_base_json",
        },
    }


def select_profile_knowledge_items(query: str, profile: dict | None = None, stage: dict | None = None, top_k: int = 3) -> List[dict]:
    items = _load_student_knowledge_items()
    if not items:
        items = _load_knowledge_points_items() or _load_textbook_knowledge_items()
    if not items:
        return []

    terms = []
    for token in _tokenize_query(query or "") + _profile_terms(profile, stage):
        if token and token not in terms:
            terms.append(token)

    weak_points = clean_text((profile or {}).get("weak_points") or "")
    stage_points = [clean_text(item) for item in ((stage or {}).get("stage_points") or []) if clean_text(item)]
    scored = []
    for index, item in enumerate(items):
        score = _score_item(terms, item) + _primary_bonus(item)
        title_norm = _normalize_string(item.get("normalized_title") or item.get("title") or "")
        related_norm = [_normalize_string(v) for v in (item.get("related_knowledge_titles") or [])]
        parent_norm = [_normalize_string(v) for v in (item.get("parent_titles") or [])]
        child_norm = [_normalize_string(v) for v in (item.get("child_titles") or [])]
        for point in stage_points:
            point_norm = _normalize_string(point)
            if point_norm and point_norm == title_norm:
                score += 16.0
            elif point_norm and (point_norm in related_norm or point_norm in parent_norm or point_norm in child_norm):
                score += 7.0
        weak_norm = _normalize_string(weak_points)
        if weak_norm and weak_norm == title_norm:
            score += 10.0
        elif weak_norm and weak_norm in related_norm:
            score += 4.0
        if score <= 0:
            continue
        scored.append((score, index, item))

    scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)
    return [_student_item_to_chunk(item, index, score) for score, index, item in scored[:top_k]]


def _fallback_search(query: str, top_k: int = 3) -> List[dict]:
    query_tokens = _tokenize_query(query)
    items = _load_student_knowledge_items()
    if not items:
        items = _load_knowledge_points_items() or _load_textbook_knowledge_items()
    if not items:
        return []
    scored = []
    for index, item in enumerate(items):
        score = _score_item(query_tokens, item)
        if score <= 0:
            continue
        scored.append((score, index, item))
    scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)
    return [
        {
            "source": Path(item.get("source_file") or "knowledge").name,
            "chunk_index": index,
            "content": item["content"],
            "score": round(float(score), 4),
            "retrieval_mode": "keyword",
            "metadata": {
                "title": item["title"],
                "source": item.get("source_file") or "",
                "section_title": item.get("section_path", [""])[-1] if item.get("section_path") else "",
                "section_path": item.get("section_path") or [],
                "pages": item.get("pages") or [],
                "chunk_id": item.get("chunk_id") or item.get("knowledge_id") or f"keyword_{index}",
                "knowledge_point": item["title"],
                "knowledge_type": item.get("knowledge_type") or "",
                "tags": item.get("tags") or [],
                "learning_location": item.get("learning_location") or {},
                "content_preview": item.get("content_preview") or "",
                "related_knowledge_titles": item.get("related_knowledge_titles") or [],
                "retrieval_source": item.get("retrieval_source") or "student_knowledge_base_json",
            },
        }
        for score, index, item in scored[:top_k]
    ]


def retrieve_knowledge_items(query: str, top_k: int = 3) -> List[dict]:
    if not query or not query.strip():
        return []
    try:
        collection = _get_collection()
        if collection.count() == 0:
            build_vector_db()
        if collection.count() > 0:
            embedding = _get_embedding_model().encode([query], normalize_embeddings=True).tolist()[0]
            result = collection.query(query_embeddings=[embedding], n_results=top_k)
            docs = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            items = []
            for index, doc in enumerate(docs):
                metadata = metadatas[index] if index < len(metadatas) else {}
                items.append(
                    {
                        "source": metadata.get("source", "unknown"),
                        "chunk_index": metadata.get("chunk_index", index),
                        "content": doc,
                        "score": distances[index] if index < len(distances) else None,
                        "retrieval_mode": "vector",
                        "metadata": metadata,
                    }
                )
            if items:
                return items
    except Exception:
        pass
    return _fallback_search(query, top_k=top_k)


def format_knowledge_items(items: List[dict]) -> str:
    if not items:
        return "未检索到对应知识库片段。"
    blocks = []
    for item in items:
        metadata = item.get("metadata") or {}
        title = metadata.get("title") or "知识点"
        section_path = metadata.get("section_path") or []
        if not isinstance(section_path, list):
            section_path = [str(section_path)] if section_path else []
        pages = _pages_text(metadata.get("pages") or [])
        blocks.append(
            "\n".join(
                [
                    f"标题：{title}",
                    f"章节路径：{' / '.join(section_path) if section_path else '未标注'}",
                    f"页码：{pages or '未标注'}",
                    f"内容：{clean_text(item.get('content') or '')}",
                ]
            )
        )
    return "\n\n".join(blocks)


def retrieve_knowledge(query: str, top_k: int = 3) -> str:
    return format_knowledge_items(retrieve_knowledge_items(query, top_k=top_k))


def _extract_image_path(text: str) -> str:
    absolute = re.search(r"([A-Za-z]:\\[^\n\r，。；]+?\.(?:png|jpg|jpeg|webp|gif))", text, flags=re.IGNORECASE)
    if absolute:
        return absolute.group(1).strip()
    relative = re.search(r"(images[\\/][^\n\r，。；]+?\.(?:png|jpg|jpeg|webp|gif))", text, flags=re.IGNORECASE)
    if relative:
        return relative.group(1).strip()
    return ""


def _extract_image_lines(content: str, limit: int = 8) -> List[dict]:
    images = []
    for line in str(content).splitlines():
        if not re.search(r"\.(?:png|jpg|jpeg|webp|gif)", line, flags=re.IGNORECASE):
            continue
        caption = line.strip()
        path = _extract_image_path(caption)
        if not path:
            continue
        images.append({"caption": caption, "path": path})
        if len(images) >= limit:
            break
    return images


def _merge_images(*groups: List[dict], limit: int = 12) -> List[dict]:
    merged = []
    seen = set()
    for group in groups:
        for image in group or []:
            path = str(image.get("path") or "").strip()
            caption = str(image.get("caption") or "").strip()
            key = path or caption
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(image)
            if len(merged) >= limit:
                return merged
    return merged


def _safe_context_chunk(item: dict) -> dict:
    metadata = item.get("metadata") or {}
    section_path = metadata.get("section_path") or []
    if not isinstance(section_path, list):
        section_path = [str(section_path)] if section_path else []
    learning_location = metadata.get("learning_location") or _safe_learning_location({"section_path": section_path, "pages": metadata.get("pages") or []})
    return {
        "title": metadata.get("title", ""),
        "content": clean_text(item.get("content") or ""),
        "content_preview": clean_text(metadata.get("content_preview") or item.get("content") or "")[:220],
        "section_path": section_path,
        "learning_location": learning_location,
        "pages": metadata.get("pages") or [],
        "source_file": metadata.get("source") or item.get("source") or "",
    }


def build_resource_context(query: str, top_k: int = 6, profile: dict | None = None, stage: dict | None = None) -> dict:
    items = select_profile_knowledge_items(query, profile=profile, stage=stage, top_k=top_k)
    chunks = [_safe_context_chunk(item) for item in items]
    images = []
    for item in items:
        images.extend(_extract_image_lines(item.get("content", "")))
    primary_knowledge = chunks[0] if chunks else {}
    return {
        "primary_knowledge": primary_knowledge,
        "retrieved_chunks": chunks,
        "chapter_context": _load_chapter_index(),
        "images": _merge_images(images, limit=12),
        "debug": {
            "query": query,
            "retrieved_count": len(chunks),
            "kb_root": str(generated_kb_dir()),
            "preferred_source": "student_knowledge_base_json",
            "primary_knowledge_title": primary_knowledge.get("title") if primary_knowledge else "",
        },
    }


def rag_status() -> dict:
    student_items = _load_student_knowledge_items()
    chapter_index = _load_chapter_index()
    question_items = _load_question_items()
    chunk_count = 0
    mode = _last_build_result.get("retrieval_mode", "unknown")
    try:
        collection = _get_collection()
        chunk_count = collection.count()
        if chunk_count > 0:
            mode = "vector"
    except Exception:
        chunk_count = len(_fallback_chunks) or len(_build_fallback_chunks())
        mode = "keyword"
    return {
        "source_dir": config.RAG_SOURCE_DIR,
        "student_knowledge_base_dir": str(student_knowledge_base_dir()),
        "chapter_index_dir": str(chapter_index_dir()),
        "questions_dir": str(questions_json_dir()),
        "vector_dir": config.RAG_VECTOR_DIR,
        "document_count": len(list_source_documents()),
        "student_knowledge_count": len(student_items),
        "chapter_count": len(((chapter_index.get("courses") or [{}])[0].get("chapters") or [])) if chapter_index else 0,
        "question_count": len(question_items),
        "chunk_count": chunk_count or len(_fallback_chunks),
        "retrieval_mode": mode,
        "last_build": _last_build_result,
    }


class RAGService:
    def build_index(self) -> dict:
        return build_vector_db()

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        return retrieve_knowledge_items(query, top_k=top_k)


rag_service = RAGService()
