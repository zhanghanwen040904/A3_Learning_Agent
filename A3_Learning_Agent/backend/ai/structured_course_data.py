import json
import re
from pathlib import Path
from typing import Dict, List

from config import config


def generated_kb_dir() -> Path:
    return Path(config.RAG_SOURCE_DIR).parent


def semantic_json_dir() -> Path:
    return generated_kb_dir() / "raw_extracted" / "software_engineering" / "semantic_json"


def clean_text(text: str) -> str:
    text = str(text or "").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_title(title: str) -> str:
    title = str(title or "").strip()
    title = re.sub(r"^\[第\d+页\]\s*", "", title)
    title = re.sub(r"^[onq•·]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^第[\d一二三四五六七八九十百]+章\s*", "", title)
    title = re.sub(r"^\d+[\.、]\s*", "", title)
    title = re.sub(r"^\d+\s+", "", title)
    title = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", title)
    title = re.sub(r"\s{2,}", " ", title)
    return title.strip("：:；;，, ")


def normalize_line(line: str) -> str:
    line = str(line or "").strip()
    line = re.sub(r"\[第\d+页\]\s*", "", line)
    line = re.sub(r"^[onq•·]\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s+[onq•·]\s+", "；", line, flags=re.IGNORECASE)
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


def is_noise_line(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return True
    if stripped.startswith(("课程：", "来源文件：", "知识路径：", "起始页：")):
        return True
    if re.fullmatch(r"\[第\d+页\].*", stripped):
        return True
    if re.fullmatch(r"[onq•·\-\s]+", stripped, flags=re.IGNORECASE):
        return True
    if stripped in {"是", "否", "客户", "顾客", "需求", "输入", "输出", "项目小组", "设计小组", "分析员", "系统分"}:
        return True
    if len(stripped) <= 2:
        return True
    return False


def preprocess_text(text: str) -> str:
    lines = clean_text(text).splitlines()
    cleaned: List[str] = []
    previous = ""
    for raw in lines:
        line = normalize_line(raw)
        if is_noise_line(line):
            continue
        if line == previous:
            continue
        cleaned.append(line)
        previous = line
    return "\n".join(cleaned).strip()


def split_sentences(text: str) -> List[str]:
    text = preprocess_text(text)
    if not text:
        return []
    parts = re.split(r"[。！？!?]\s*|\n+", text)
    return [part.strip(" \n-:：；;，,") for part in parts if part.strip()]


def summarize_text(text: str, max_sentences: int = 2) -> str:
    sentences = split_sentences(text)
    if sentences:
        return "；".join(sentences[:max_sentences])
    return preprocess_text(text)[:180]


def is_useful_title(title: str) -> bool:
    normalized = normalize_title(title)
    if len(normalized) <= 2:
        return False
    if normalized in {"SDLC", "课堂讨论", "课堂练习", "课堂练习2", "作业", "举例", "案例"}:
        return False
    if normalized.startswith(("o ", "q", "1.", "2.", "3.", "4.", "5.")):
        return False
    if re.match(r"^\d+\s*", normalized):
        return False
    if re.fullmatch(r"\d+(\.\d+)*", normalized):
        return False
    return True


def is_useful_chunk(title: str, content: str) -> bool:
    normalized_title = normalize_title(title)
    cleaned_content = preprocess_text(content)
    if not is_useful_title(normalized_title):
        return False
    if len(cleaned_content) < 20:
        return False
    noise_ratio = cleaned_content.count("；") / max(len(cleaned_content), 1)
    if noise_ratio > 0.2:
        return False
    return True


def load_semantic_chunks() -> List[Dict]:
    root = semantic_json_dir()
    if not root.exists():
        return []

    chunks: List[Dict] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        source_name = path.stem.replace("_semantic", "") + ".pdf"
        course = payload.get("course", "")
        for item in payload.get("knowledge_chunks", []):
            metadata = item.get("metadata") or {}
            title = metadata.get("knowledge_point") or metadata.get("section_title") or ""
            content = item.get("content_text") or ""
            if not is_useful_chunk(title, content):
                continue

            section_path = metadata.get("section_path") or []
            normalized_path = [normalize_title(part) for part in section_path if normalize_title(part)]
            normalized_title = normalize_title(title)
            cleaned_content = preprocess_text(content)
            chunks.append(
                {
                    "chunk_id": item.get("chunk_id") or "",
                    "source": source_name,
                    "course": course,
                    "knowledge_point": normalized_title,
                    "section_title": normalize_title(metadata.get("section_title") or normalized_title),
                    "section_path": normalized_path,
                    "section_path_text": " > ".join(normalized_path),
                    "pages": metadata.get("pages") or [],
                    "knowledge_type": metadata.get("knowledge_type") or "",
                    "tags": [normalize_title(tag) for tag in (metadata.get("tags") or []) if normalize_title(tag)],
                    "content": cleaned_content,
                    "summary": summarize_text(cleaned_content),
                }
            )
    return chunks
