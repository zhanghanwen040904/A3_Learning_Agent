import re
import shutil
from pathlib import Path
from typing import List

try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None
    Settings = None
try:
    from docx import Document
except Exception:
    Document = None
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

from config import config

_COLLECTION_NAME = "ai_intro_course"
_embedding_model = None
_chroma_client = None
_collection = None
_fallback_chunks: List[dict] = []
_last_build_result = {"status": "not_built", "chunks": 0, "message": "知识库尚未构建"}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), text)
    text = re.sub(r"[#>*_`~\-]{1,}", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、,.!?;:()（）\[\]{}<>/=+\-*\n\s]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


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


def _read_txt(path: Path) -> str:
    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_docx(path: Path) -> str:
    if Document is None:
        return ""
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def list_source_documents() -> List[dict]:
    source_dir = Path(config.RAG_SOURCE_DIR)
    source_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}:
            documents.append({"name": path.name, "path": str(path.relative_to(source_dir)), "suffix": path.suffix.lower(), "size": path.stat().st_size})
    return documents


def _load_source_documents() -> List[dict]:
    source_dir = Path(config.RAG_SOURCE_DIR)
    source_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in source_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf", ".docx"}:
            continue
        if path.suffix.lower() in {".txt", ".md"}:
            raw = _read_txt(path)
        elif path.suffix.lower() == ".pdf":
            raw = _read_pdf(path)
        else:
            raw = _read_docx(path)
        cleaned = clean_text(raw)
        if cleaned:
            documents.append({"source": path.name, "text": cleaned})
    return documents


def _split_text(text: str, chunk_size: int = 600, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0
    text = text.strip()
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(end - overlap, start + 1)
    return chunks


def _build_fallback_chunks() -> List[dict]:
    chunks = []
    for doc_index, doc in enumerate(_load_source_documents()):
        for chunk_index, chunk in enumerate(_split_text(doc["text"])):
            chunks.append({"source": doc["source"], "chunk_index": chunk_index, "content": chunk, "doc_index": doc_index})
    return chunks


def _tokenize_query(query: str) -> List[str]:
    query = clean_text(query)
    words = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}", query)
    domain_terms = ["监督学习", "无监督学习", "分类", "回归", "聚类", "降维", "机器学习", "深度学习", "神经网络", "人工智能", "知识表示", "搜索", "伦理", "安全"]
    for term in domain_terms:
        if term in query and term not in words:
            words.append(term)
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
        score = sum(content.count(token) for token in tokens)
        if score == 0:
            score = sum(1 for char in query if char.strip() and char in content) / max(len(query), 1)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"source": item["source"], "chunk_index": item["chunk_index"], "content": item["content"], "score": round(float(score), 4), "retrieval_mode": "keyword"}
        for score, item in scored[:top_k]
        if score > 0
    ] or [
        {"source": item["source"], "chunk_index": item["chunk_index"], "content": item["content"], "score": 0, "retrieval_mode": "keyword"}
        for _, item in scored[:top_k]
    ]


def build_vector_db(force: bool = False) -> dict:
    global _fallback_chunks, _last_build_result
    _fallback_chunks = _build_fallback_chunks()
    if not _fallback_chunks:
        _last_build_result = {"status": "empty", "documents": 0, "chunks": 0, "message": "source_docs目录下没有可构建的课程文档"}
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
            _last_build_result = {"status": "loaded", "chunks": collection.count(), "fallback_chunks": len(_fallback_chunks), "message": "向量库已存在，已直接加载"}
            return _last_build_result

        ids, texts, metadatas = [], [], []
        for index, item in enumerate(_fallback_chunks):
            ids.append(f"doc_{item['doc_index']}_chunk_{item['chunk_index']}")
            texts.append(item["content"])
            metadatas.append({"source": item["source"], "chunk_index": item["chunk_index"]})
        embeddings = _get_embedding_model().encode(texts, normalize_embeddings=True).tolist()
        collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        _last_build_result = {"status": "created", "documents": len(list_source_documents()), "chunks": len(texts), "fallback_chunks": len(_fallback_chunks), "retrieval_mode": "vector", "message": "向量库构建完成"}
        return _last_build_result
    except Exception as exc:
        _last_build_result = {"status": "fallback", "documents": len(list_source_documents()), "chunks": len(_fallback_chunks), "fallback_chunks": len(_fallback_chunks), "retrieval_mode": "keyword", "message": "向量库暂不可用，已启用关键词检索降级模式", "warning": str(exc)}
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
                items.append({"source": metadata.get("source", "unknown"), "chunk_index": metadata.get("chunk_index", index), "content": doc, "score": distances[index] if index < len(distances) else None, "retrieval_mode": "vector"})
            if items:
                return items
    except Exception:
        pass
    return _fallback_search(query, top_k=top_k)


def format_knowledge_items(items: List[dict]) -> str:
    if not items:
        return "未检索到课程知识库内容，请先向 rag_data/source_docs 添加《人工智能导论》教材资料。"
    return "\n\n".join(f"【教材来源：{item['source']}｜片段{item['chunk_index']}｜模式：{item.get('retrieval_mode', 'unknown')}】\n{item['content']}" for item in items)


def retrieve_knowledge(query: str, top_k: int = 3) -> str:
    return format_knowledge_items(retrieve_knowledge_items(query, top_k=top_k))


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
    return {"source_dir": config.RAG_SOURCE_DIR, "vector_dir": config.RAG_VECTOR_DIR, "documents": documents, "document_count": len(documents), "chunk_count": chunk_count or len(_fallback_chunks), "retrieval_mode": mode, "last_build": _last_build_result}


class RAGService:
    def build_index(self) -> dict:
        return build_vector_db()

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        return retrieve_knowledge_items(query, top_k=top_k)


rag_service = RAGService()
