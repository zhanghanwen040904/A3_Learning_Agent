import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, List

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


_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "software_engineering_knowledge")
_GENERATED_KB_DIR = os.getenv("GENERATED_KNOWLEDGE_DIR", r"E:\知识问答\MY\batch_outputs_llm_vision")

_embedding_model = None
_chroma_client = None
_collection = None
_fallback_chunks: List[dict] = []
_last_build_result = {"status": "not_built", "chunks": 0, "message": "知识库尚未构建"}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), str(text))
    text = re.sub(r"[#>*_`~]{1,}", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generated_kb_dir() -> Path:
    return Path(_GENERATED_KB_DIR)


def reset_rag_cache() -> None:
    global _chroma_client, _collection
    _collection = None
    _chroma_client = None


def _get_embedding_model():
    global _embedding_model
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers 未安装，使用关键词检索降级模式")
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.RAG_EMBEDDING_MODEL)
    return _embedding_model


def _get_collection():
    global _chroma_client, _collection
    if chromadb is None or Settings is None:
        raise RuntimeError("chromadb 未安装，使用关键词检索降级模式")
    if _collection is None:
        vector_dir = Path(config.RAG_VECTOR_DIR)
        vector_dir.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(vector_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _metadata_value(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _load_json_safely(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def list_source_documents() -> List[dict]:
    base = generated_kb_dir()
    documents = []
    semantic_dir = base / "semantic_json"
    tree_dir = base / "knowledge_tree_json"
    for path in sorted(semantic_dir.glob("*.json")) if semantic_dir.exists() else []:
        documents.append(
            {"name": path.name, "path": str(path), "suffix": ".json", "size": path.stat().st_size, "source_type": "generated_semantic_json"}
        )
    for path in sorted(tree_dir.glob("*_knowledge_tree.json")) if tree_dir.exists() else []:
        documents.append(
            {"name": path.name, "path": str(path), "suffix": ".json", "size": path.stat().st_size, "source_type": "generated_knowledge_tree"}
        )
    return documents


def _image_summary(images: list[dict]) -> str:
    lines = []
    for image in images[:5]:
        caption = str(image.get("caption") or "").strip()
        path = str(image.get("absolute_path") or image.get("path") or "").strip()
        image_type = str(image.get("image_type") or "").strip()
        if caption or path:
            lines.append(f"{image_type}：{caption}（{path}）")
    return "\n".join(lines)


def _chunk_to_document(chunk: dict, source_name: str, course: str) -> dict | None:
    metadata = chunk.get("metadata", {}) or {}
    title = str(metadata.get("knowledge_point") or metadata.get("section_title") or "").strip()
    content = clean_text(str(chunk.get("content_text") or ""))
    if not title and not content:
        return None
    section_path = metadata.get("section_path", []) or []
    pages = metadata.get("pages", []) or []
    images = metadata.get("images", []) or []
    image_text = _image_summary(images)
    text_parts = [
        f"【课程】{course}",
        f"【来源】{source_name}",
        f"【知识点】{title}",
        f"【章节路径】{' > '.join(str(item) for item in section_path)}",
        f"【页码】{', '.join(str(page) for page in pages)}",
        "【正文】",
        content,
    ]
    if image_text:
        text_parts.extend(["【相关图片】", image_text])
    return {
        "source": source_name,
        "text": "\n".join(part for part in text_parts if part),
        "metadata": {
            "source_type": "generated_semantic_json",
            "source": source_name,
            "chunk_id": str(chunk.get("chunk_id") or ""),
            "title": title,
            "course": course,
            "section_path": " > ".join(str(item) for item in section_path),
            "pages": ",".join(str(page) for page in pages),
            "image_count": len(images),
        },
    }


def _load_generated_semantic_documents(base_dir: Path) -> List[dict]:
    semantic_dir = base_dir / "semantic_json"
    documents = []
    if not semantic_dir.exists():
        return documents
    for path in sorted(semantic_dir.glob("*.json")):
        data = _load_json_safely(path)
        course = str(data.get("course") or "软件工程")
        chunks = data.get("knowledge_chunks") or data.get("rule_chunks") or []
        for chunk in chunks:
            doc = _chunk_to_document(chunk, path.name, course)
            if doc:
                documents.append(doc)
    return documents


def _load_generated_tree_documents(base_dir: Path) -> List[dict]:
    tree_dir = base_dir / "knowledge_tree_json"
    documents = []
    if not tree_dir.exists():
        return documents
    for path in sorted(tree_dir.glob("*_knowledge_tree.json")):
        data = _load_json_safely(path)
        course = str(data.get("course") or "软件工程")
        points = data.get("knowledge_points") or []
        relations = data.get("relations") or []
        title_by_id = {point.get("chunk_id"): point.get("title", "") for point in points}
        relation_lines = []
        for edge in relations[:180]:
            source = title_by_id.get(edge.get("source"), edge.get("source"))
            target = title_by_id.get(edge.get("target"), edge.get("target"))
            relation_lines.append(f"{source} --{edge.get('type')}--> {target}")
        text = "\n".join(
            [
                f"【课程】{course}",
                f"【知识树】{path.stem}",
                f"【知识点数量】{len(points)}",
                f"【关系数量】{len(relations)}",
                "【知识点列表】",
                "\n".join(str(point.get("title", "")) for point in points),
                "【知识关系】",
                "\n".join(relation_lines),
            ]
        )
        documents.append(
            {
                "source": path.name,
                "text": clean_text(text),
                "metadata": {
                    "source_type": "generated_knowledge_tree",
                    "source": path.name,
                    "course": course,
                    "knowledge_point_count": len(points),
                    "relation_count": len(relations),
                },
            }
        )
    return documents


def _load_source_documents() -> List[dict]:
    base = generated_kb_dir()
    documents: List[dict] = []
    if base.exists():
        documents.extend(_load_generated_semantic_documents(base))
        documents.extend(_load_generated_tree_documents(base))
    return documents


def _build_fallback_chunks() -> List[dict]:
    chunks = []
    for doc_index, doc in enumerate(_load_source_documents()):
        item = {
            "source": doc["source"],
            "chunk_index": 0,
            "content": doc["text"],
            "doc_index": doc_index,
            "metadata": doc.get("metadata", {}),
        }
        chunks.append(item)
    return chunks


def _tokenize_query(query: str) -> List[str]:
    query = clean_text(query)
    words = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}", query)
    return list(dict.fromkeys(words))


def _fallback_search(query: str, top_k: int = 3) -> List[dict]:
    global _fallback_chunks
    if not _fallback_chunks:
        _fallback_chunks = _build_fallback_chunks()
    if not _fallback_chunks:
        return []
    tokens = _tokenize_query(query)
    scored = []
    for item in _fallback_chunks:
        content = item["content"]
        title = str(item.get("metadata", {}).get("title", ""))
        searchable = f"{title}\n{content}"
        score = sum(searchable.count(token) for token in tokens)
        if score == 0:
            score = sum(1 for char in query if char.strip() and char in searchable) / max(len(query), 1)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "source": item["source"],
            "chunk_index": item["chunk_index"],
            "content": item["content"],
            "score": round(float(score), 4),
            "retrieval_mode": "keyword",
            "metadata": item.get("metadata", {}),
        }
        for score, item in scored[:top_k]
        if score > 0
    ]


def build_vector_db(force: bool = False, force_rebuild: bool = False) -> dict:
    global _fallback_chunks, _last_build_result
    force = force or force_rebuild
    _fallback_chunks = _build_fallback_chunks()
    if not _fallback_chunks:
        _last_build_result = {"status": "empty", "documents": 0, "chunks": 0, "message": "未找到可构建的课程资料"}
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
        if collection.count() > 0 and not force:
            _last_build_result = {
                "status": "loaded",
                "collection": _COLLECTION_NAME,
                "chunks": collection.count(),
                "fallback_chunks": len(_fallback_chunks),
                "generated_knowledge_dir": str(generated_kb_dir()),
                "message": "向量库已存在，已直接加载",
            }
            return _last_build_result

        ids, texts, metadatas = [], [], []
        for index, item in enumerate(_fallback_chunks):
            metadata = dict(item.get("metadata") or {})
            ids.append(f"doc_{item['doc_index']}_chunk_{item['chunk_index']}_{index}")
            texts.append(item["content"])
            metadata["source"] = item["source"]
            metadata["chunk_index"] = item["chunk_index"]
            metadatas.append({key: _metadata_value(value) for key, value in metadata.items()})
        embeddings = _get_embedding_model().encode(texts, normalize_embeddings=True).tolist()
        collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        _last_build_result = {
            "status": "created",
            "collection": _COLLECTION_NAME,
            "documents": len(list_source_documents()),
            "chunks": len(texts),
            "fallback_chunks": len(_fallback_chunks),
            "retrieval_mode": "vector",
            "generated_knowledge_dir": str(generated_kb_dir()),
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
            "generated_knowledge_dir": str(generated_kb_dir()),
            "message": "向量库暂不可用，已启用关键词检索降级模式",
            "warning": str(exc),
        }
        return _last_build_result


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
        return "未检索到课程知识库内容，请检查 batch_outputs_llm_vision。"
    fragments = []
    for item in items:
        metadata = item.get("metadata") or {}
        title = metadata.get("title", "")
        header = f"【教材来源：{item['source']}；片段：{item['chunk_index']}；模式：{item.get('retrieval_mode', 'unknown')}】"
        if title:
            header += f"\n【知识点】{title}"
        fragments.append(f"{header}\n{item['content']}")
    return "\n\n".join(fragments)


def retrieve_knowledge(query: str, top_k: int = 3) -> str:
    return format_knowledge_items(retrieve_knowledge_items(query, top_k=top_k))


def _find_tree_for_source(source_name: str) -> dict:
    tree_dir = generated_kb_dir() / "knowledge_tree_json"
    if not tree_dir.exists():
        return {}
    stem = Path(str(source_name)).stem
    candidates = [
        tree_dir / f"{stem.replace('_semantic', '')}_knowledge_tree.json",
        tree_dir / f"{stem}_knowledge_tree.json",
    ]
    for path in candidates:
        if path.exists():
            return _load_json_safely(path)
    for path in tree_dir.glob("*_knowledge_tree.json"):
        if stem.replace("_semantic", "") in path.stem:
            return _load_json_safely(path)
    return {}


def _tree_context(tree: dict, focus_ids: set[str], limit: int = 30) -> dict:
    if not tree:
        return {"knowledge_points": [], "relations": []}
    points = tree.get("knowledge_points") or []
    relations = tree.get("relations") or []
    title_by_id = {str(point.get("chunk_id")): str(point.get("title") or "") for point in points}
    related_ids = set(focus_ids)
    for edge in relations:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in focus_ids or target in focus_ids:
            related_ids.add(source)
            related_ids.add(target)

    selected_points = []
    for point in points:
        chunk_id = str(point.get("chunk_id") or "")
        if chunk_id in related_ids or len(selected_points) < 8:
            selected_points.append(
                {
                    "id": chunk_id,
                    "title": point.get("title", ""),
                    "pages": point.get("pages", []),
                    "image_count": len(point.get("images") or []),
                }
            )
        if len(selected_points) >= limit:
            break

    selected_relations = []
    for edge in relations:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in related_ids or target in related_ids:
            selected_relations.append(
                {
                    "source": title_by_id.get(source, source),
                    "target": title_by_id.get(target, target),
                    "type": edge.get("type", ""),
                }
            )
        if len(selected_relations) >= limit:
            break
    return {"knowledge_points": selected_points, "relations": selected_relations}


def _extract_image_lines(content: str, limit: int = 8) -> list[dict]:
    images = []
    for line in str(content).splitlines():
        if "jpeg" not in line.lower() and "png" not in line.lower() and "jpg" not in line.lower():
            continue
        caption = line.strip()
        path_match = re.search(r"([A-Za-z]:\\[^\s，,；;）)]+?\.(?:png|jpg|jpeg))", caption, flags=re.IGNORECASE)
        images.append({"caption": caption, "path": path_match.group(1) if path_match else ""})
        if len(images) >= limit:
            break
    return images


def _image_ref_from_raw(image: dict) -> dict:
    path = str(image.get("absolute_path") or image.get("path") or "").strip()
    if path and not Path(path).is_absolute():
        path = str((generated_kb_dir() / path).resolve())
    return {
        "caption": str(image.get("caption") or image.get("image_type") or "知识库图片").strip(),
        "path": path,
        "page": image.get("page", ""),
        "image_type": str(image.get("image_type") or "").strip(),
    }


def _images_for_chunk(source_name: str, chunk_id: str, limit: int = 6) -> list[dict]:
    if not source_name or not chunk_id:
        return []
    semantic_dir = generated_kb_dir() / "semantic_json"
    source_path = semantic_dir / source_name
    if not source_path.exists():
        return []
    data = _load_json_safely(source_path)
    images = []
    for chunk in data.get("knowledge_chunks") or data.get("rule_chunks") or []:
        if str(chunk.get("chunk_id") or "") != str(chunk_id):
            continue
        metadata = chunk.get("metadata") or {}
        for image in metadata.get("images") or []:
            ref = _image_ref_from_raw(image)
            if ref.get("path"):
                images.append(ref)
        break
    return images[:limit]


def _merge_images(*groups: list[dict], limit: int = 12) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for image in group or []:
            path = str(image.get("path") or "").strip()
            caption = str(image.get("caption") or "").strip()
            if not path:
                continue
            key = path or caption
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(image)
            if len(merged) >= limit:
                return merged
    return merged


def _student_context_text(content: str) -> str:
    """Keep only student-useful lines from an indexed chunk."""
    lines = []
    for raw_line in str(content).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("【来源】"):
            continue
        if line.startswith("【课程】"):
            continue
        if "retrieval_mode" in line or "chunk_id" in line or "score" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def build_resource_context(query: str, top_k: int = 6) -> dict:
    items = retrieve_knowledge_items(query, top_k=top_k)
    source_names = []
    focus_ids: set[str] = set()
    chunks = []
    images = []
    for item in items:
        metadata = item.get("metadata") or {}
        source = str(item.get("source") or metadata.get("source") or "")
        chunk_id = str(metadata.get("chunk_id") or "")
        if source:
            source_names.append(source)
        if chunk_id:
            focus_ids.add(chunk_id)
        inline_images = _extract_image_lines(item.get("content", ""))
        chunk_images = _images_for_chunk(source, chunk_id)
        image_refs = _merge_images(chunk_images, inline_images, limit=8)
        images.extend(image_refs)
        chunks.append(
            {
                "title": metadata.get("title", ""),
                "source": source,
                "section_path": metadata.get("section_path", ""),
                "pages": metadata.get("pages", ""),
                "chunk_id": chunk_id,
                "content": _student_context_text(str(item.get("content") or ""))[:1200],
                "images": image_refs,
            }
        )

    tree_map = {}
    for source in dict.fromkeys(source_names):
        tree = _find_tree_for_source(source)
        if tree:
            tree_map[source] = _tree_context(tree, focus_ids)

    return {
        "query": query,
        "knowledge_base_dir": str(generated_kb_dir()),
        "retrieved_chunks": chunks,
        "knowledge_tree": tree_map,
        "images": _merge_images(images, limit=12),
        "generation_rules": [
            "只能依据 retrieved_chunks、knowledge_tree 和 images 生成学习资源。",
            "优先围绕 query 对应的核心知识点，不要把多个无关章节硬拼在一起。",
            "只要 images 非空，必须在资源内容中输出“配图建议：caption（path）”。",
            "输出给学生时隐藏 chunk_id、score、retrieval_mode、JSON 字段名等内部信息。",
            "讲解要短、清楚、可读，避免直接罗列大量来源路径。",
            "允许整理、改写、举例，但不得编造教材不存在的事实、页码、图片路径。",
            "当知识库覆盖不足时，需要明确说明未覆盖。",
        ],
    }


def rag_status() -> dict:
    documents = list_source_documents()
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
        "generated_knowledge_dir": str(generated_kb_dir()),
        "vector_dir": config.RAG_VECTOR_DIR,
        "documents": documents,
        "document_count": len(documents),
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
