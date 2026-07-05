"""Standalone textbook PDF chunking, optional LLM refinement, and MySQL ingestion.

This file is intentionally under MY/ and does not modify DeepTutor source code.

Pipeline:
1. Parse PDF with PyMuPDF.
2. Remove repeated headers, footers, page numbers, and TOC-like pages.
3. Build a lightweight section tree from heading patterns.
4. Create local semantic chunks by section, paragraph, sentence, size, and overlap.
5. Optionally call an OpenAI-compatible LLM API to refine knowledge boundaries.
6. Optionally call an OpenAI-compatible LLM API to infer prerequisite/next relations.
7. Optionally call an OpenAI-compatible embedding API.
8. Optionally write nodes/chunks to MySQL.

Dry run, no API, no MySQL:
    python MY/ingest_pdf_to_mysql.py --pdf "C:\\path\\book.pdf" --course "软件工程" ^
      --dry-run --export-json "E:\\DeepTutor-main\\MY\\chunk_test.json"

LLM refinement + relation generation, still no MySQL:
    python MY/ingest_pdf_to_mysql.py --pdf "C:\\path\\book.pdf" --course "软件工程" ^
      --dry-run --use-llm-boundaries --generate-relations ^
      --llm-base-url "https://api.example.com/v1" --llm-api-key "KEY" --llm-model "MODEL" ^
      --export-json "E:\\DeepTutor-main\\MY\\chunk_llm_test.json"

Embedding + MySQL:
    python MY/ingest_pdf_to_mysql.py --pdf "C:\\path\\book.pdf" --course "软件工程" ^
      --embed --embedding-base-url "https://api.example.com/v1" ^
      --embedding-api-key "KEY" --embedding-model "EMBED_MODEL" ^
      --host 127.0.0.1 --user root --password "MYSQL_PASSWORD" ^
      --database deeptutor_project --create-database --init-db --reset-course
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fitz
except ImportError as exc:
    raise SystemExit("Missing dependency: PyMuPDF. Run: python -m pip install PyMuPDF") from exc

try:
    import mysql.connector
except ImportError:
    mysql = None  # type: ignore[assignment]


CN_NUMERAL = "\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u96f6\u3007\u4e24"
HEADING_PATTERNS: tuple[tuple[int, re.Pattern[str]], ...] = (
    (1, re.compile(rf"^\s*\u7b2c[{CN_NUMERAL}\d]+[\u7ae0\u8282\u7bc7]\s*.{{0,80}}$")),
    (1, re.compile(r"^\s*chapter\s+\d+[\s:.-]+.{0,80}$", re.I)),
    (2, re.compile(r"^\s*\d+\.\d+\s+.{1,80}$")),
    (3, re.compile(r"^\s*\d+\.\d+\.\d+\s+.{1,80}$")),
    (2, re.compile(rf"^\s*[{CN_NUMERAL}]+[\u3001.]\s*.{{1,80}}$")),
    (3, re.compile(r"^\s*[(\uff08]\d+[)\uff09]\s*.{1,80}$")),
)
SENTENCE_END_RE = re.compile(r"(?<=[\u3002\uff01\uff1f!?;；])")


@dataclass
class TextBlock:
    page: int
    text: str
    bbox: tuple[float, float, float, float]
    font_size: float


@dataclass
class Section:
    node_id: str
    parent_id: str | None
    title: str
    level: int
    chapter_id: str
    start_page: int
    path: list[str]
    paragraphs: list[dict[str, Any]]


@dataclass
class APIConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    max_retries: int = 2
    retry_base_delay: float = 3.0
    request_delay: float = 0.0


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_repeat_key(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"\d+", "#", text)
    text = re.sub(r"\s+", " ", text)
    return text[:200]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(part) for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def is_page_number(text: str) -> bool:
    text = normalize_text(text)
    return bool(
        re.fullmatch(r"\d{1,4}", text)
        or re.fullmatch(r"[-\u2014]\s*\d{1,4}\s*[-\u2014]", text)
        or re.fullmatch(r"page\s*\d{1,4}", text, flags=re.I)
        or re.fullmatch(r"\u7b2c\s*\d{1,4}\s*\u9875", text)
    )


class APIRequestError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise APIRequestError(
            f"HTTP {exc.code} from API: {body[:1000]}",
            status=exc.code,
            body=body,
        ) from exc


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


class OpenAICompatibleLLMClient:
    """Small OpenAI-compatible chat client for boundary and relation tasks."""

    def __init__(self, config: APIConfig) -> None:
        self.config = config
        self.url = config.base_url.rstrip("/") + "/chat/completions"

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.request_delay > 0:
                    time.sleep(self.config.request_delay)
                result = post_json(self.url, payload, self.config.api_key, self.config.timeout)
                content = result["choices"][0]["message"]["content"]
                return extract_json_object(content)
            except (KeyError, json.JSONDecodeError, urllib.error.URLError, APIRequestError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    retry_after = self.config.retry_base_delay * (2**attempt)
                    if isinstance(exc, APIRequestError) and exc.status == 429:
                        retry_after = max(retry_after, 20.0 * (attempt + 1))
                    time.sleep(retry_after)
                    continue
        raise RuntimeError(f"LLM API failed: {last_error}") from last_error


class GeminiLLMClient:
    """Gemini generateContent client for boundary and relation tasks."""

    def __init__(self, config: APIConfig) -> None:
        self.config = config
        base_url = config.base_url.rstrip("/") or "https://generativelanguage.googleapis.com/v1beta"
        model = config.model
        if not model.startswith("models/"):
            model = f"models/{model}"
        self.url = f"{base_url}/{model}:generateContent?key={config.api_key}"

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.request_delay > 0:
                    time.sleep(self.config.request_delay)
                result = post_json(self.url, payload, "", self.config.timeout)
                parts = result["candidates"][0]["content"]["parts"]
                content = "".join(str(part.get("text", "")) for part in parts)
                return extract_json_object(content)
            except (KeyError, json.JSONDecodeError, urllib.error.URLError, APIRequestError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    retry_after = self.config.retry_base_delay * (2**attempt)
                    if isinstance(exc, APIRequestError) and exc.status == 429:
                        retry_after = max(retry_after, 20.0 * (attempt + 1))
                    time.sleep(retry_after)
                    continue
        raise RuntimeError(f"Gemini API failed: {last_error}") from last_error


class OpenAICompatibleEmbeddingClient:
    """Small OpenAI-compatible embedding client."""

    def __init__(self, config: APIConfig, batch_size: int = 16) -> None:
        self.config = config
        self.batch_size = batch_size
        self.url = config.base_url.rstrip("/") + "/embeddings"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            payload = {"model": self.config.model, "input": batch}
            last_error: Exception | None = None
            for attempt in range(self.config.max_retries + 1):
                try:
                    if self.config.request_delay > 0:
                        time.sleep(self.config.request_delay)
                    result = post_json(self.url, payload, self.config.api_key, self.config.timeout)
                    batch_vectors = [item["embedding"] for item in result["data"]]
                    vectors.extend(batch_vectors)
                    break
                except (KeyError, urllib.error.URLError, APIRequestError) as exc:
                    last_error = exc
                    if attempt < self.config.max_retries:
                        retry_after = self.config.retry_base_delay * (2**attempt)
                        if isinstance(exc, APIRequestError) and exc.status == 429:
                            retry_after = max(retry_after, 20.0 * (attempt + 1))
                        time.sleep(retry_after)
                        continue
                    raise RuntimeError(f"Embedding API failed: {last_error}") from last_error
        return vectors


def extract_blocks(page: fitz.Page, page_number: int) -> list[TextBlock]:
    raw = page.get_text("dict")
    blocks: list[TextBlock] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines: list[str] = []
        sizes: list[float] = []
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            line_text = normalize_text(line_text)
            if line_text:
                lines.append(line_text)
            for span in line.get("spans", []):
                if span.get("size"):
                    sizes.append(float(span["size"]))
        if not lines:
            continue
        bbox = tuple(float(v) for v in block.get("bbox", (0, 0, 0, 0)))
        blocks.append(
            TextBlock(
                page=page_number,
                text=normalize_text("\n".join(lines)),
                bbox=bbox,  # type: ignore[arg-type]
                font_size=max(sizes) if sizes else 0.0,
            )
        )
    return sorted(blocks, key=lambda item: (item.bbox[1], item.bbox[0]))


def detect_repeated_headers_footers(doc: fitz.Document) -> tuple[set[str], set[str]]:
    top: dict[str, int] = {}
    bottom: dict[str, int] = {}
    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        height = float(page.rect.height)
        for block in extract_blocks(page, page_index + 1):
            key = normalize_repeat_key(block.text)
            if not key or is_page_number(key):
                continue
            _, y0, _, y1 = block.bbox
            if y1 / height <= 0.12:
                top[key] = top.get(key, 0) + 1
            if y0 / height >= 0.88:
                bottom[key] = bottom.get(key, 0) + 1
    min_count = max(3, int(max(doc.page_count, 1) * 0.45))
    return (
        {key for key, count in top.items() if count >= min_count},
        {key for key, count in bottom.items() if count >= min_count},
    )


def is_toc_page(blocks: list[TextBlock]) -> bool:
    lines = [line for block in blocks for line in block.text.splitlines()]
    if not lines:
        return False
    head = "\n".join(lines[:8])
    if re.search(r"\u76ee\s*\u5f55|contents|table of contents", head, re.I):
        return True
    toc_like = 0
    for line in lines:
        line = normalize_text(line)
        if re.search(r"\.{2,}\s*\d{1,4}$", line):
            toc_like += 1
        elif re.search(r"\s{2,}\d{1,4}$", line) and len(line) <= 90:
            toc_like += 1
        elif re.search(rf"\u7b2c[{CN_NUMERAL}\d]+[\u7ae0\u8282\u7bc7].*\d{{1,4}}$", line):
            toc_like += 1
        elif re.search(r"^\s*\d+(\.\d+)*\s+.+\s+\d{1,4}$", line):
            toc_like += 1
    return toc_like >= 4 or toc_like / max(len(lines), 1) >= 0.35


def clean_blocks(
    page: fitz.Page,
    page_number: int,
    headers: set[str],
    footers: set[str],
) -> list[TextBlock]:
    cleaned: list[TextBlock] = []
    for block in extract_blocks(page, page_number):
        key = normalize_repeat_key(block.text)
        if key in headers or key in footers:
            continue
        lines = [
            normalize_text(line)
            for line in block.text.splitlines()
            if normalize_text(line) and not is_page_number(line)
        ]
        if not lines:
            continue
        cleaned.append(
            TextBlock(
                page=page_number,
                text=normalize_text("\n".join(lines)),
                bbox=block.bbox,
                font_size=block.font_size,
            )
        )
    return cleaned


def heading_level(text: str, block: TextBlock, page_baseline: float) -> int | None:
    compact = normalize_text(text).replace("\n", " ")
    if len(compact) > 90:
        return None
    for level, pattern in HEADING_PATTERNS:
        if pattern.match(compact):
            return level
    if page_baseline and block.font_size >= page_baseline * 1.35 and 2 <= len(compact) <= 60:
        return 2
    return None


def parse_pdf(pdf_path: Path, course: str, skip_toc: bool) -> list[Section]:
    doc = fitz.open(str(pdf_path))
    headers, footers = detect_repeated_headers_footers(doc)
    root = Section(
        node_id=stable_id("node", course, "root"),
        parent_id=None,
        title=course,
        level=0,
        chapter_id=stable_id("chapter", course, "root"),
        start_page=1,
        path=[course],
        paragraphs=[],
    )
    sections = [root]
    stack = [root]
    heading_count = 0

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        page = doc.load_page(page_index)
        raw_blocks = extract_blocks(page, page_number)
        if skip_toc and is_toc_page(raw_blocks):
            continue
        blocks = clean_blocks(page, page_number, headers, footers)
        font_sizes = sorted(block.font_size for block in blocks if block.font_size > 0)
        baseline = font_sizes[len(font_sizes) // 2] if font_sizes else 0.0

        for block in blocks:
            text = normalize_text(block.text).replace("\n", " ")
            level = heading_level(text, block, baseline)
            if level is not None:
                heading_count += 1
                while stack and stack[-1].level >= level:
                    stack.pop()
                parent = stack[-1] if stack else root
                chapter_id = stable_id("chapter", course, text) if level <= 1 else parent.chapter_id
                section = Section(
                    node_id=stable_id("node", course, page_number, heading_count, text),
                    parent_id=parent.node_id,
                    title=text,
                    level=level,
                    chapter_id=chapter_id,
                    start_page=page_number,
                    path=parent.path + [text],
                    paragraphs=[],
                )
                sections.append(section)
                stack.append(section)
                continue
            current = stack[-1] if stack else root
            current.paragraphs.append(
                {
                    "page": page_number,
                    "text": text,
                    "bbox": block.bbox,
                    "font_size": block.font_size,
                }
            )
    doc.close()
    return sections


def split_long_text(text: str, max_chars: int) -> list[str]:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return [text] if text else []
    sentences = [part.strip() for part in SENTENCE_END_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current}{sentence}" if current else sentence
    if current:
        chunks.append(current.strip())
    return chunks


def make_rule_chunks(section: Section, max_chars: int, overlap: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    parts: list[str] = []
    pages: list[int] = []

    def flush() -> None:
        nonlocal parts, pages
        text = "\n\n".join(parts).strip()
        if text:
            chunks.append({"text": text, "pages": sorted(set(pages))})
        parts = []
        pages = []

    for paragraph in section.paragraphs:
        text = paragraph["text"].strip()
        if not text:
            continue
        if len(text) > max_chars:
            flush()
            for piece in split_long_text(text, max_chars):
                chunks.append({"text": piece, "pages": [paragraph["page"]]})
            continue
        current_len = len("\n\n".join(parts))
        if parts and current_len + len(text) + 2 > max_chars:
            flush()
            if overlap > 0 and chunks:
                tail = chunks[-1]["text"][-overlap:].strip()
                if tail:
                    parts.append(tail)
        parts.append(text)
        pages.append(paragraph["page"])
    flush()

    result: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        result.append(
            {
                "chunk_id": stable_id("chunk", section.node_id, index, chunk["text"][:80]),
                "node_id": section.node_id,
                "chapter_id": section.chapter_id,
                "content_text": chunk["text"],
                "embedding": None,
                "metadata": {
                    "course": section.path[0] if section.path else "",
                    "section_title": section.title,
                    "section_path": section.path,
                    "section_level": section.level,
                    "start_page": section.start_page,
                    "pages": chunk["pages"],
                    "chunk_index": index,
                    "chunk_method": "rule",
                    "knowledge_point": section.title,
                    "prerequisite_node_ids": [],
                    "next_node_ids": [],
                },
            }
        )
    return result


def refine_chunks_with_llm(
    chunks: list[dict[str, Any]],
    llm: OpenAICompatibleLLMClient,
    *,
    max_chars: int,
    max_chunks: int = 0,
) -> list[dict[str, Any]]:
    """Use an LLM to split each rule chunk into knowledge-point chunks."""

    system_prompt = (
        "You split textbook text into knowledge-point chunks for RAG ingestion. "
        "Return only JSON. Do not invent facts. Keep original wording as much as possible."
    )
    refined: list[dict[str, Any]] = []
    processed = 0
    for chunk in chunks:
        if max_chunks > 0 and processed >= max_chunks:
            refined.append(chunk)
            continue
        text = chunk["content_text"]
        if len(text) < max_chars * 0.7:
            refined.append(chunk)
            continue
        user_prompt = json.dumps(
            {
                "instruction": (
                    "Split the text into coherent knowledge points. "
                    "Each item should be self-contained, normally 300-900 Chinese characters. "
                    "Do not split formulas/definitions/examples away from their explanation."
                ),
                "required_json_schema": {
                    "chunks": [
                        {
                            "title": "knowledge point title",
                            "text": "chunk text",
                            "tags": ["optional keyword"],
                        }
                    ]
                },
                "section_path": chunk["metadata"].get("section_path", []),
                "text": text,
            },
            ensure_ascii=False,
        )
        result = llm.complete_json(system_prompt, user_prompt)
        processed += 1
        items = result.get("chunks")
        if not isinstance(items, list) or not items:
            refined.append(chunk)
            continue
        for idx, item in enumerate(items, start=1):
            item_text = normalize_text(str(item.get("text", "")))
            if not item_text:
                continue
            new_chunk = json.loads(json.dumps(chunk, ensure_ascii=False))
            new_chunk["chunk_id"] = stable_id("chunk", chunk["chunk_id"], "llm", idx, item_text[:80])
            new_chunk["content_text"] = item_text
            new_chunk["embedding"] = None
            new_chunk["metadata"]["chunk_method"] = "llm_boundary"
            new_chunk["metadata"]["knowledge_point"] = str(item.get("title") or chunk["metadata"]["section_title"])
            new_chunk["metadata"]["tags"] = item.get("tags") if isinstance(item.get("tags"), list) else []
            new_chunk["metadata"]["parent_rule_chunk_id"] = chunk["chunk_id"]
            refined.append(new_chunk)
    return refined


def generate_relations_with_llm(
    chunks: list[dict[str, Any]],
    llm: OpenAICompatibleLLMClient,
    *,
    window_size: int = 20,
) -> list[dict[str, Any]]:
    """Ask an LLM to infer prerequisite/next relations among nearby chunks."""

    system_prompt = (
        "You infer prerequisite and next-knowledge relations among textbook chunks. "
        "Use only provided chunk IDs and titles. Return only JSON."
    )
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    for start in range(0, len(chunks), window_size):
        window = chunks[start : start + window_size]
        candidates = [
            {
                "chunk_id": chunk["chunk_id"],
                "title": chunk["metadata"].get("knowledge_point")
                or chunk["metadata"].get("section_title"),
                "section_path": chunk["metadata"].get("section_path", []),
                "summary_text": chunk["content_text"][:300],
            }
            for chunk in window
        ]
        user_prompt = json.dumps(
            {
                "instruction": (
                    "For each chunk, identify prerequisite_chunk_ids and next_chunk_ids "
                    "from this candidate list only. Keep relations sparse and high-confidence."
                ),
                "required_json_schema": {
                    "relations": [
                        {
                            "chunk_id": "existing id",
                            "prerequisite_chunk_ids": ["existing id"],
                            "next_chunk_ids": ["existing id"],
                        }
                    ]
                },
                "chunks": candidates,
            },
            ensure_ascii=False,
        )
        result = llm.complete_json(system_prompt, user_prompt)
        for relation in result.get("relations", []):
            chunk_id = relation.get("chunk_id")
            if chunk_id not in by_id:
                continue
            valid_pre = [
                cid
                for cid in relation.get("prerequisite_chunk_ids", [])
                if isinstance(cid, str) and cid in by_id and cid != chunk_id
            ]
            valid_next = [
                cid
                for cid in relation.get("next_chunk_ids", [])
                if isinstance(cid, str) and cid in by_id and cid != chunk_id
            ]
            by_id[chunk_id]["metadata"]["prerequisite_node_ids"] = valid_pre
            by_id[chunk_id]["metadata"]["next_node_ids"] = valid_next
    return chunks


def embed_chunks(
    chunks: list[dict[str, Any]],
    embedding_client: OpenAICompatibleEmbeddingClient,
) -> list[dict[str, Any]]:
    """Generate embeddings and attach them to chunk['embedding']."""

    texts = [chunk["content_text"] for chunk in chunks]
    vectors = embedding_client.embed_texts(texts)
    if len(vectors) != len(chunks):
        raise RuntimeError(f"Embedding count mismatch: expected {len(chunks)}, got {len(vectors)}")
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["embedding"] = vector
        chunk["metadata"]["embedding_dim"] = len(vector)
    return chunks


def build_payload(
    pdf_path: Path,
    course: str,
    sections: list[Section],
    *,
    max_chars: int,
    overlap: int,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for section in sections:
        nodes.append(
            {
                "node_id": section.node_id,
                "parent_id": section.parent_id,
                "title": section.title,
                "level": section.level,
                "chapter_id": section.chapter_id,
                "start_page": section.start_page,
                "path": section.path,
                "paragraph_count": len(section.paragraphs),
            }
        )
        chunks.extend(make_rule_chunks(section, max_chars=max_chars, overlap=overlap))
    return make_payload_dict(pdf_path, course, max_chars, overlap, nodes, chunks)


def make_payload_dict(
    pdf_path: Path,
    course: str,
    max_chars: int,
    overlap: int,
    nodes: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_file": str(pdf_path),
        "course": course,
        "max_chars": max_chars,
        "overlap": overlap,
        "outline_nodes": nodes,
        "knowledge_chunks": chunks,
        "stats": {
            "outline_node_count": len(nodes),
            "chunk_count": len(chunks),
            "min_chunk_chars": min((len(chunk["content_text"]) for chunk in chunks), default=0),
            "max_chunk_chars": max((len(chunk["content_text"]) for chunk in chunks), default=0),
            "avg_chunk_chars": (
                round(sum(len(chunk["content_text"]) for chunk in chunks) / len(chunks), 2)
                if chunks
                else 0
            ),
            "embedded_chunk_count": sum(1 for chunk in chunks if chunk.get("embedding")),
        },
    }


SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS user_profile (
      user_id VARCHAR(64) PRIMARY KEY,
      academic_major VARCHAR(255),
      knowledge_base JSON,
      last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS course_knowledge_graph (
      node_id VARCHAR(128) PRIMARY KEY,
      parent_id VARCHAR(128),
      title VARCHAR(512) NOT NULL,
      level INT DEFAULT 0,
      chapter_id VARCHAR(128),
      metadata JSON,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_parent_id (parent_id),
      INDEX idx_chapter_id (chapter_id)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_chunks (
      chunk_id VARCHAR(128) PRIMARY KEY,
      node_id VARCHAR(128),
      chapter_id VARCHAR(128),
      content_text MEDIUMTEXT NOT NULL,
      embedding JSON,
      metadata JSON,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FULLTEXT INDEX ft_content_text (content_text),
      INDEX idx_node_id (node_id),
      INDEX idx_chapter_id (chapter_id)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_tasks (
      task_id VARCHAR(128) PRIMARY KEY,
      user_id VARCHAR(64),
      agent_type VARCHAR(64),
      status VARCHAR(32),
      result_url TEXT,
      payload JSON,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_user_id (user_id),
      INDEX idx_status (status)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
)


def connect(args: argparse.Namespace, *, with_database: bool = True):
    if mysql is None:
        raise SystemExit(
            "Missing dependency: mysql-connector-python. "
            "Run: python -m pip install mysql-connector-python"
        )
    config = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password or os.getenv("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if with_database:
        config["database"] = args.database
    return mysql.connector.connect(**config)


def ensure_database(args: argparse.Namespace) -> None:
    with connect(args, with_database=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{args.database}` "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()


def ensure_schema(conn) -> None:
    cursor = conn.cursor()
    for statement in SCHEMA_SQL:
        cursor.execute(statement)
    conn.commit()


def reset_course(conn, course: str) -> None:
    cursor = conn.cursor()
    course_pattern = f'%"{course}"%'
    cursor.execute(
        "DELETE FROM knowledge_chunks WHERE JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.course')) = %s",
        (course,),
    )
    cursor.execute(
        "DELETE FROM course_knowledge_graph WHERE JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.course')) = %s "
        "OR metadata LIKE %s",
        (course, course_pattern),
    )
    conn.commit()


def write_to_mysql(conn, nodes: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> tuple[int, int]:
    cursor = conn.cursor()
    for node in nodes:
        metadata = {
            "course": node["path"][0] if node.get("path") else "",
            "path": node.get("path", []),
            "start_page": node.get("start_page"),
            "paragraph_count": node.get("paragraph_count", 0),
        }
        cursor.execute(
            """
            INSERT INTO course_knowledge_graph
              (node_id, parent_id, title, level, chapter_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              parent_id = VALUES(parent_id),
              title = VALUES(title),
              level = VALUES(level),
              chapter_id = VALUES(chapter_id),
              metadata = VALUES(metadata)
            """,
            (
                node["node_id"],
                node["parent_id"],
                node["title"],
                node["level"],
                node["chapter_id"],
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
    for chunk in chunks:
        cursor.execute(
            """
            INSERT INTO knowledge_chunks
              (chunk_id, node_id, chapter_id, content_text, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              node_id = VALUES(node_id),
              chapter_id = VALUES(chapter_id),
              content_text = VALUES(content_text),
              embedding = VALUES(embedding),
              metadata = VALUES(metadata)
            """,
            (
                chunk["chunk_id"],
                chunk["node_id"],
                chunk["chapter_id"],
                chunk["content_text"],
                json.dumps(chunk["embedding"]) if chunk.get("embedding") else None,
                json.dumps(chunk["metadata"], ensure_ascii=False),
            ),
        )
    conn.commit()
    return len(nodes), len(chunks)


def require_llm_args(args: argparse.Namespace) -> APIConfig:
    env_key = "GEMINI_API_KEY" if args.llm_provider == "gemini" else "LLM_API_KEY"
    api_key = args.llm_api_key or os.getenv(env_key, "")
    if not api_key or not args.llm_model:
        raise SystemExit(
            f"LLM options required: --llm-api-key/{env_key} --llm-model"
        )
    base_url = args.llm_base_url
    if args.llm_provider == "gemini" and not base_url:
        base_url = "https://generativelanguage.googleapis.com/v1beta"
    if args.llm_provider == "openai_compat" and not base_url:
        raise SystemExit("OpenAI-compatible mode requires --llm-base-url")
    return APIConfig(
        base_url=base_url,
        api_key=api_key,
        model=args.llm_model,
        timeout=args.api_timeout,
        max_retries=args.api_retries,
        retry_base_delay=args.api_retry_delay,
        request_delay=args.api_delay,
    )


def build_llm_client(args: argparse.Namespace):
    config = require_llm_args(args)
    if args.llm_provider == "gemini":
        return GeminiLLMClient(config)
    return OpenAICompatibleLLMClient(config)


def require_embedding_args(args: argparse.Namespace) -> APIConfig:
    api_key = args.embedding_api_key or os.getenv("EMBEDDING_API_KEY", "")
    if not args.embedding_base_url or not api_key or not args.embedding_model:
        raise SystemExit(
            "Embedding options required: "
            "--embedding-base-url --embedding-api-key/EMBEDDING_API_KEY --embedding-model"
        )
    return APIConfig(
        base_url=args.embedding_base_url,
        api_key=api_key,
        model=args.embedding_model,
        timeout=args.api_timeout,
        max_retries=args.api_retries,
        retry_base_delay=args.api_retry_delay,
        request_delay=args.api_delay,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone PDF chunker, API enricher, and MySQL ingester.")
    parser.add_argument("--pdf", required=True, help="PDF file path")
    parser.add_argument("--course", required=True, help="Course/book name")
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--no-skip-toc", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Only parse/chunk/export; do not use MySQL")
    parser.add_argument("--export-json", help="Write parsed outline and chunks to JSON")
    parser.add_argument("--print-samples", type=int, default=3)

    parser.add_argument("--use-llm-boundaries", action="store_true")
    parser.add_argument("--generate-relations", action="store_true")
    parser.add_argument("--llm-provider", choices=["openai_compat", "gemini"], default="openai_compat")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--api-timeout", type=int, default=60)
    parser.add_argument("--api-retries", type=int, default=3)
    parser.add_argument("--api-retry-delay", type=float, default=3.0)
    parser.add_argument("--api-delay", type=float, default=1.0, help="Delay between API requests in seconds")
    parser.add_argument("--max-llm-chunks", type=int, default=0, help="Limit LLM boundary calls; 0 means all")
    parser.add_argument("--relation-window-size", type=int, default=10)

    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--embedding-base-url", default="")
    parser.add_argument("--embedding-api-key", default="")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--embedding-batch-size", type=int, default=16)

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="", help="MySQL password or MYSQL_PASSWORD env")
    parser.add_argument("--database", default="deeptutor_project")
    parser.add_argument("--create-database", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--reset-course", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    sections = parse_pdf(pdf_path, args.course, skip_toc=not args.no_skip_toc)
    payload = build_payload(
        pdf_path,
        args.course,
        sections,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    nodes = payload["outline_nodes"]
    chunks = payload["knowledge_chunks"]

    llm = None
    if args.use_llm_boundaries or args.generate_relations:
        llm = build_llm_client(args)

    if args.use_llm_boundaries:
        chunks = refine_chunks_with_llm(
            chunks,
            llm,  # type: ignore[arg-type]
            max_chars=args.max_chars,
            max_chunks=args.max_llm_chunks,
        )

    if args.generate_relations:
        chunks = generate_relations_with_llm(
            chunks,
            llm,  # type: ignore[arg-type]
            window_size=args.relation_window_size,
        )

    if args.embed:
        embedder = OpenAICompatibleEmbeddingClient(
            require_embedding_args(args),
            batch_size=args.embedding_batch_size,
        )
        chunks = embed_chunks(chunks, embedder)

    payload = make_payload_dict(pdf_path, args.course, args.max_chars, args.overlap, nodes, chunks)

    if args.export_json:
        export_path = Path(args.export_json)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = payload["stats"]
    if args.dry_run:
        print(
            f"Dry run complete: {pdf_path.name}\n"
            f"Course: {args.course}\n"
            f"Outline nodes: {stats['outline_node_count']}\n"
            f"Chunks: {stats['chunk_count']}\n"
            f"Embedded chunks: {stats['embedded_chunk_count']}\n"
            f"Chunk chars: min={stats['min_chunk_chars']}, "
            f"avg={stats['avg_chunk_chars']}, max={stats['max_chunk_chars']}"
        )
        if args.export_json:
            print(f"Exported JSON: {args.export_json}")
        for chunk in chunks[: max(args.print_samples, 0)]:
            text = chunk["content_text"].replace("\n", " ")
            print(
                "\n--- sample chunk ---\n"
                f"id: {chunk['chunk_id']}\n"
                f"path: {' > '.join(chunk['metadata']['section_path'])}\n"
                f"method: {chunk['metadata'].get('chunk_method')}\n"
                f"knowledge_point: {chunk['metadata'].get('knowledge_point')}\n"
                f"pages: {chunk['metadata']['pages']}\n"
                f"chars: {len(chunk['content_text'])}\n"
                f"text: {text[:500]}"
            )
        return 0

    if args.create_database:
        ensure_database(args)

    conn = connect(args)
    try:
        if args.init_db:
            ensure_schema(conn)
        if args.reset_course:
            reset_course(conn, args.course)
        node_count, chunk_count = write_to_mysql(conn, nodes, chunks)
    finally:
        conn.close()

    print(
        f"Ingested PDF into MySQL: {pdf_path.name}\n"
        f"Course: {args.course}\n"
        f"Outline nodes: {node_count}\n"
        f"Chunks: {chunk_count}\n"
        f"Embedded chunks: {stats['embedded_chunk_count']}\n"
        f"Database: {args.database}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
