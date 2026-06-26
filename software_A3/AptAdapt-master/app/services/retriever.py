"""Chroma 向量知识库 — 多课程支持，按课程切换 collection"""
import json
import os
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedding_client import EmbeddingClient
from ..courses import DEFAULT_COURSE, get_collection_name

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "chroma_db")
BASE_CHUNKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base")


class Retriever:
    """Chroma 向量检索器 — 按课程隔离 collection"""

    def __init__(self, course_id: str = DEFAULT_COURSE, chroma_dir: Optional[str] = None):
        self._client = chromadb.PersistentClient(
            path=chroma_dir or os.path.abspath(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedder = EmbeddingClient()
        self.switch_course(course_id)

    def switch_course(self, course_id: str):
        """切换到指定课程的 collection"""
        collection_name = get_collection_name(course_id)
        self._collection = self._client.get_or_create_collection(name=collection_name)
        self._course_id = course_id

    @property
    def count(self) -> int:
        return self._collection.count()

    @property
    def course_id(self) -> str:
        return self._course_id

    def populate(self, chunks: Optional[list[dict]] = None) -> int:
        if chunks is None:
            chunks = _load_chunks(self._course_id)

        if not chunks:
            return 0

        texts = [c["content"] for c in chunks]
        ids = [c["id"] for c in chunks]
        metadatas = [
            {
                "title": c.get("title", ""),
                "chapter": c.get("chapter", ""),
                "keywords": ", ".join(c.get("keywords", [])),
                "difficulty": c.get("difficulty", "medium"),
            }
            for c in chunks
        ]

        print(f"[{self._course_id}] 正在向量化 {len(texts)} 个知识片段...")
        embeddings = self._embedder.embed(texts)
        print(f"[{self._course_id}] 向量化完成，维度: {len(embeddings[0])}")

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        print(f"[{self._course_id}] 已入库 {len(ids)} 个片段")
        return len(ids)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if self._collection.count() == 0:
            return []

        query_embedding = self._embedder.embed_single(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                chunks.append({
                    "id": chunk_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "title": meta.get("title", ""),
                    "chapter": meta.get("chapter", ""),
                    "keywords": meta.get("keywords", ""),
                    "difficulty": meta.get("difficulty", ""),
                    "score": round(1.0 - distance, 4) if distance else 0,
                })

        return chunks

    def clear(self):
        self._client.delete_collection(name=self._collection.name)
        self._collection = self._client.get_or_create_collection(name=self._collection.name)


def _load_chunks(course_id: str) -> list[dict]:
    path = os.path.join(BASE_CHUNKS_DIR, course_id, "chunks.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"知识片段文件不存在: {path}")
        return []


# ── 便捷函数（保留旧接口兼容） ──

_retrievers: dict[str, Retriever] = {}


def _get_retriever(course_id: str = DEFAULT_COURSE) -> Retriever:
    if course_id not in _retrievers:
        _retrievers[course_id] = Retriever(course_id=course_id)
    return _retrievers[course_id]


def retrieve(query: str, top_k: int = 5, course_id: str = DEFAULT_COURSE) -> list[dict]:
    """检索指定课程的知识片段。容错: 空库或 API 失败返回 []"""
    try:
        r = _get_retriever(course_id)
        if r.course_id != course_id:
            r.switch_course(course_id)
        if r.count == 0:
            return []
        return r.retrieve(query, top_k)
    except Exception as e:
        print(f"[Retriever:{course_id}] 检索失败，降级为空: {e}")
        return []


def populate_knowledge_base(course_id: str = DEFAULT_COURSE,
                            chunks: Optional[list[dict]] = None) -> int:
    return _get_retriever(course_id).populate(chunks)


if __name__ == "__main__":
    import sys
    cid = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_COURSE

    if len(sys.argv) > 1 and sys.argv[1] == "--populate":
        print(f"=== [{cid}] 向量知识库入库 ===")
        n = populate_knowledge_base(cid)
        print(f"[{cid}] 入库完成，共 {n} 条")

    print(f"\n=== [{cid}] 检索测试 ===")
    results = retrieve("Cache 映射方式", top_k=3, course_id=cid)
    for r in results:
        print(f"\n[{r['id']}] {r['title']} (score: {r['score']})")
        print(f"  {r['content'][:80]}...")
