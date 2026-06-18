import re
from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings
from docx import Document
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from config import config

_COLLECTION_NAME = "ai_intro_course"
_embedding_model = None
_chroma_client = None
_collection = None


def clean_text(text: str) -> str:
    """清理教材文本。

    功能：去除 Markdown 标记、特殊控制字符和多余空行，保留中文、英文、数字、常见标点与代码符号。
    输入：原始文本字符串。
    输出：清理后的文本字符串。
    """
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), text)
    text = re.sub(r"[#>*_`~\-]{1,}", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、,.!?;:()（）\[\]{}<>/=+\-*\n\s]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _get_embedding_model() -> SentenceTransformer:
    """加载 BGE-small-zh-v1.5 嵌入模型。

    功能：懒加载本地或在线 sentence-transformers 模型。
    输入：无。
    输出：SentenceTransformer 模型实例。
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.RAG_EMBEDDING_MODEL)
    return _embedding_model


def _get_collection():
    """获取 Chroma 向量库集合。

    功能：创建或加载持久化 Chroma 向量库。
    输入：无。
    输出：Chroma collection 对象。
    """
    global _chroma_client, _collection
    if _collection is None:
        vector_dir = Path(config.RAG_VECTOR_DIR)
        vector_dir.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(vector_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _read_txt(path: Path) -> str:
    """读取 txt 文件。

    功能：自动尝试 UTF-8 和 GBK 编码读取文本。
    输入：txt 文件路径。
    输出：文件文本内容。
    """
    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    """读取 pdf 文件。

    功能：提取 PDF 每页文本并拼接。
    输入：pdf 文件路径。
    输出：PDF 文本内容。
    """
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    """读取 docx 文件。

    功能：提取 Word 文档段落文本。
    输入：docx 文件路径。
    输出：Word 文本内容。
    """
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _load_source_documents() -> List[dict]:
    """加载课程知识库原始文档。

    功能：读取 rag_data/source_docs 下所有 txt、pdf、docx 文件。
    输入：无。
    输出：包含文件名和文本内容的文档列表。
    """
    source_dir = Path(config.RAG_SOURCE_DIR)
    source_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in source_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".pdf", ".docx"}:
            continue
        if path.suffix.lower() == ".txt":
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
    """分块教材文本。

    功能：按固定字符长度切分文本，并保留 50 字符重叠，提升检索上下文连续性。
    输入：文本、分块长度、重叠长度。
    输出：文本块列表。
    """
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


def build_vector_db() -> dict:
    """构建并持久化 Chroma 向量库。

    功能：读取课程资料，清洗、分块、使用 BGE-small-zh-v1.5 生成嵌入，写入 rag_data/vector_db。
    输入：无。
    输出：包含状态、文档数量、分块数量的字典。
    """
    collection = _get_collection()
    if collection.count() > 0:
        return {"status": "loaded", "chunks": collection.count(), "message": "向量库已存在，已直接加载"}

    documents = _load_source_documents()
    if not documents:
        return {"status": "empty", "chunks": 0, "message": "source_docs目录下没有可构建的课程文档"}

    ids = []
    texts = []
    metadatas = []
    for doc_index, doc in enumerate(documents):
        for chunk_index, chunk in enumerate(_split_text(doc["text"])):
            ids.append(f"doc_{doc_index}_chunk_{chunk_index}")
            texts.append(chunk)
            metadatas.append({"source": doc["source"], "chunk_index": chunk_index})

    embeddings = _get_embedding_model().encode(texts, normalize_embeddings=True).tolist()
    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    return {"status": "created", "documents": len(documents), "chunks": len(texts), "message": "向量库构建完成"}


def retrieve_knowledge(query: str, top_k: int = 3) -> str:
    """检索最相关教材原文片段。

    功能：根据查询词在 Chroma 知识库中检索教材内容，返回拼接后的原文片段，用于防幻觉生成。
    输入：query 查询词；top_k 返回片段数量，默认 3。
    输出：包含来源和原文片段的字符串。
    """
    if not query or not query.strip():
        return ""
    collection = _get_collection()
    if collection.count() == 0:
        build_vector_db()
    if collection.count() == 0:
        return "未检索到课程知识库内容，请先向 rag_data/source_docs 添加《人工智能导论》教材资料。"

    embedding = _get_embedding_model().encode([query], normalize_embeddings=True).tolist()[0]
    result = collection.query(query_embeddings=[embedding], n_results=top_k)
    docs = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    fragments = []
    for index, doc in enumerate(docs):
        source = metadatas[index].get("source", "unknown") if index < len(metadatas) else "unknown"
        fragments.append(f"【教材来源：{source}】\n{doc}")
    return "\n\n".join(fragments)


class RAGService:
    """RAG 服务兼容类。

    功能：为旧代码提供 build_index 和 search 兼容方法。
    输入：查询词和 top_k。
    输出：结构化检索结果。
    """

    def build_index(self) -> dict:
        return build_vector_db()

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        text = retrieve_knowledge(query, top_k=top_k)
        return [{"title": "教材原文片段", "content": text, "score": ""}]


rag_service = RAGService()
