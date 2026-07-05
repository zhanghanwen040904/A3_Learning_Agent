"""Generate semantic chunks and a knowledge tree from PDF JSON.

Input is the ``*_pdf.json`` produced by ``pdf_to_json.py``. Output files are
written beside the input JSON by default:

* ``*_semantic.json``: semantic chunks, optional LLM boundary refinement, and
  prerequisite/next relations.
* ``*_knowledge_tree.json``: tree nodes, chunk links, and relation edges.
* ``*_knowledge_tree.mmd``: Mermaid mindmap preview.

The script does not write MySQL. Configure the LLM with environment variables
instead of hard-coding secrets:

PowerShell:
    $env:LLM_API_KEY="your-key"

Typical XFYun OpenAI-compatible call:
    python MY/semantic_slice_tree.py --input-json book_pdf.json ^
      --llm-base-url "https://maas-api.cn-huabei-1.xf-yun.com/v2" ^
      --llm-model "Qwen3.6-35B-A3B" --use-llm-boundaries --generate-relations
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from ingest_pdf_to_mysql import (
    APIConfig,
    extract_json_object,
    make_payload_dict,
    normalize_text,
    stable_id,
)


class FlexibleOpenAICompatibleLLMClient:
    """OpenAI-compatible chat client with optional response_format support."""

    def __init__(
        self,
        config: APIConfig,
        *,
        use_response_format: bool = True,
        verify_ssl: bool = True,
    ) -> None:
        self.config = config
        self.url = config.base_url.rstrip("/") + "/chat/completions"
        self.use_response_format = use_response_format
        self.verify_ssl = verify_ssl

    def post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        import ssl
        import urllib.request

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=self.url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "deeptutor-semantic-slice/1.0",
            },
            method="POST",
        )
        context = None if self.verify_ssl else ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=self.config.timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8"))

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        import time
        import urllib.error

        payload: dict[str, Any] = {
            "model": self.config.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.use_response_format:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.request_delay > 0:
                    time.sleep(self.config.request_delay)
                result = self.post_json(payload)
                content = result["choices"][0]["message"]["content"]
                return extract_json_object(content)
            except (KeyError, json.JSONDecodeError, urllib.error.URLError, RuntimeError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_base_delay * (2**attempt))
                    continue
        raise RuntimeError(f"LLM API failed: {last_error}") from last_error


def load_pdf_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "rule_chunks" not in data and "knowledge_chunks" in data:
        data["rule_chunks"] = data["knowledge_chunks"]
    if "rule_chunks" not in data:
        raise SystemExit(
            "Input JSON must contain rule_chunks from pdf_to_json.py "
            "or knowledge_chunks from the old ingest script."
        )
    return data


def build_llm(args: argparse.Namespace) -> FlexibleOpenAICompatibleLLMClient:
    api_key = args.llm_api_key or os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing LLM API key. Set LLM_API_KEY or pass --llm-api-key.")
    if not args.llm_base_url:
        raise SystemExit("Missing --llm-base-url.")
    if not args.llm_model:
        raise SystemExit("Missing --llm-model.")
    return FlexibleOpenAICompatibleLLMClient(
        APIConfig(
            base_url=args.llm_base_url,
            api_key=api_key,
            model=args.llm_model,
            timeout=args.api_timeout,
            max_retries=args.api_retries,
            retry_base_delay=args.api_retry_delay,
            request_delay=args.api_delay,
        ),
        use_response_format=not args.disable_response_format,
        verify_ssl=not args.disable_ssl_verify,
    )


NOISE_TITLE_PATTERNS = [
    r"^课堂",
    r"^作业$",
    r"^练习",
    r"^案例[:：]?$",
    r"^C\.?$",
    r"^小结$",
    r"^学以致用$",
    r"^目录$",
    r"^本章",
    r"^[（(]\d+[）)]",
]
NOISE_PATH_PATTERNS = [r"^课堂", r"^作业", r"^练习", r"^学以致用", r"^案例[:：]?$", r"^小结$"]
GENERIC_SHORT_TITLES = {"软件工程", "高级软件工程", "SDLC"}


def normalize_title_key(title: str) -> str:
    text = normalize_text(title).lower()
    text = re.sub(r"^\d+(?:\.\d+)*[、.．]\s*", "", text)
    text = re.sub(r"^[\d一二三四五六七八九十]+[、.．]\s*", "", text)
    text = re.sub(r"^第[一二三四五六七八九十\d]+[章节]\s*", "", text)
    text = re.sub(r"[\s:：,，.。()（）\-_/]+", "", text)
    return text


def looks_like_toc_or_fragment(text: str) -> bool:
    compact = normalize_text(text)
    if not compact:
        return True
    if len(compact) < 20:
        return True
    bullet_hits = len(re.findall(r"(^|\s)[on]\s+", compact))
    numbered_hits = len(re.findall(r"\d+\.\d+", compact))
    if len(compact) < 140 and (bullet_hits >= 3 or numbered_hits >= 4):
        return True
    if len(compact) < 120 and re.search(r"取消项目|是否可行|是\s+否", compact):
        return True
    return False


def is_non_knowledge_chunk(chunk: dict[str, Any]) -> tuple[bool, str]:
    metadata = chunk.get("metadata", {})
    title = str(metadata.get("knowledge_point") or metadata.get("section_title") or "").strip()
    path = [str(item).strip() for item in metadata.get("section_path", []) or []]
    text = str(chunk.get("content_text") or "")
    if any(any(re.search(pattern, part) for pattern in NOISE_PATH_PATTERNS) for part in path):
        return True, "activity_or_admin_path"
    if any(re.search(pattern, title) for pattern in NOISE_TITLE_PATTERNS):
        return True, "activity_or_admin_title"
    if title == "SDLC":
        return True, "abbreviation_fragment"
    if title in GENERIC_SHORT_TITLES and looks_like_toc_or_fragment(text):
        return True, "generic_fragment"
    if looks_like_toc_or_fragment(text):
        return True, "toc_or_fragment"
    return False, ""


def filter_non_knowledge_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for chunk in chunks:
        should_remove, reason = is_non_knowledge_chunk(chunk)
        if should_remove:
            item = {
                "chunk_id": chunk.get("chunk_id"),
                "title": chunk.get("metadata", {}).get("knowledge_point")
                or chunk.get("metadata", {}).get("section_title"),
                "reason": reason,
                "pages": chunk.get("metadata", {}).get("pages", []),
                "text_preview": str(chunk.get("content_text") or "")[:160],
            }
            removed.append(item)
            continue
        kept.append(chunk)
    return kept, removed


def merge_duplicate_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        title = str(metadata.get("knowledge_point") or metadata.get("section_title") or "知识点")
        key = normalize_title_key(title)
        if not key:
            key = str(chunk.get("chunk_id"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(chunk)

    merged: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for key in order:
        items = groups[key]
        if len(items) == 1:
            merged.append(items[0])
            continue
        base = json.loads(json.dumps(items[0], ensure_ascii=False))
        titles = [
            str(item.get("metadata", {}).get("knowledge_point") or item.get("metadata", {}).get("section_title") or "")
            for item in items
        ]
        title = CounterTitle.pick(titles)
        pages = sorted(
            {
                page
                for item in items
                for page in item.get("metadata", {}).get("pages", [])
                if isinstance(page, int)
            }
        )
        texts: list[str] = []
        seen_texts: set[str] = set()
        for item in items:
            text = normalize_text(str(item.get("content_text") or ""))
            text_key = re.sub(r"\s+", "", text)
            if text and text_key not in seen_texts:
                seen_texts.add(text_key)
                texts.append(text)
        merged_id = stable_id("merged", key, "|".join(item.get("chunk_id", "") for item in items))
        base["chunk_id"] = merged_id
        base["content_text"] = "\n\n".join(texts)
        base["metadata"]["knowledge_point"] = title
        base["metadata"]["pages"] = pages
        base["metadata"]["chunk_method"] = "merged"
        base["metadata"]["merged_from_chunk_ids"] = [item.get("chunk_id") for item in items]
        base["metadata"]["prerequisite_node_ids"] = []
        base["metadata"]["next_node_ids"] = []
        merged.append(base)
        reports.append({"title": title, "merged_count": len(items), "merged_chunk_id": merged_id})
    return merged, reports


class CounterTitle:
    @staticmethod
    def pick(titles: list[str]) -> str:
        counts: dict[str, int] = {}
        for title in titles:
            title = normalize_text(title)
            counts[title] = counts.get(title, 0) + 1
        return sorted(counts, key=lambda item: (-counts[item], len(item), item))[0] if counts else "知识点"


def refine_chunks_with_llm(
    chunks: list[dict[str, Any]],
    llm: FlexibleOpenAICompatibleLLMClient,
    *,
    max_chars: int,
    max_chunks: int = 0,
) -> list[dict[str, Any]]:
    """Split rule chunks with stricter software-engineering knowledge filters."""

    system_prompt = (
        "你是软件工程课程知识图谱构建助手。你的任务是把教材/PPT文本切成可学习的核心知识点。"
        "只输出 JSON，不要输出解释。不要编造原文没有的信息。"
    )
    refined: list[dict[str, Any]] = []
    processed = 0
    for chunk in chunks:
        if max_chunks > 0 and processed >= max_chunks:
            refined.append(chunk)
            continue
        text = chunk["content_text"]
        title = chunk.get("metadata", {}).get("section_title", "")
        if len(text) < max_chars * 0.45:
            refined.append(chunk)
            continue
        user_prompt = json.dumps(
            {
                "instruction": (
                    "请从文本中抽取软件工程课程的核心知识点并重新切片。"
                    "必须过滤目录、页眉页脚、课堂讨论、课堂练习、作业、学以致用、案例标题、小结标题、"
                    "残缺流程图文字和没有完整语义的短片段。"
                    "如果文本主要是目录/课堂活动/残缺片段，请返回空 chunks。"
                    "每个知识点应包含定义、阶段、模型、特点、优缺点、适用场景、流程或方法之一。"
                    "同一概念不要拆成多个同名知识点。"
                ),
                "required_json_schema": {
                    "chunks": [
                        {
                            "title": "准确、简洁的软件工程知识点名称",
                            "type": "concept|phase|process_model|method|quality|comparison|other",
                            "text": "保留原文语义的完整知识点文本",
                            "tags": ["关键词"],
                        }
                    ]
                },
                "section_title": title,
                "section_path": chunk["metadata"].get("section_path", []),
                "text": text,
            },
            ensure_ascii=False,
        )
        result = llm.complete_json(system_prompt, user_prompt)
        processed += 1
        items = result.get("chunks")
        if not isinstance(items, list):
            refined.append(chunk)
            continue
        if not items:
            continue
        for idx, item in enumerate(items, start=1):
            item_text = normalize_text(str(item.get("text", "")))
            item_title = normalize_text(str(item.get("title", "")))
            if not item_text or not item_title:
                continue
            new_chunk = json.loads(json.dumps(chunk, ensure_ascii=False))
            new_chunk["chunk_id"] = stable_id("chunk", chunk["chunk_id"], "llm_clean", idx, item_title, item_text[:80])
            new_chunk["content_text"] = item_text
            new_chunk["embedding"] = None
            new_chunk["metadata"]["chunk_method"] = "llm_boundary_clean"
            new_chunk["metadata"]["knowledge_point"] = item_title
            new_chunk["metadata"]["knowledge_type"] = str(item.get("type") or "other")
            new_chunk["metadata"]["tags"] = item.get("tags") if isinstance(item.get("tags"), list) else []
            new_chunk["metadata"]["parent_rule_chunk_id"] = chunk["chunk_id"]
            refined.append(new_chunk)
    return refined


def generate_relations_with_llm(
    chunks: list[dict[str, Any]],
    llm: FlexibleOpenAICompatibleLLMClient,
    *,
    window_size: int = 20,
) -> list[dict[str, Any]]:
    """Infer sparse prerequisite/next relations with a stricter prompt."""

    system_prompt = (
        "你是软件工程课程知识图谱关系抽取助手。"
        "你只能使用给定 chunk_id，不能编造 ID。只输出 JSON。"
    )
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    for start in range(0, len(chunks), window_size):
        window = chunks[start : start + window_size]
        candidates = [
            {
                "chunk_id": chunk["chunk_id"],
                "title": chunk["metadata"].get("knowledge_point")
                or chunk["metadata"].get("section_title"),
                "type": chunk["metadata"].get("knowledge_type", ""),
                "pages": chunk["metadata"].get("pages", []),
                "summary_text": chunk["content_text"][:320],
            }
            for chunk in window
        ]
        user_prompt = json.dumps(
            {
                "instruction": (
                    "请为软件工程知识点生成先修关系和后继学习关系。"
                    "优先连接：概念定义 -> 阶段/模型 -> 特点 -> 优缺点 -> 适用场景。"
                    "不要连接课堂活动、作业、目录或残缺文本。"
                    "如果两个相邻知识点确实属于教材连续学习顺序，可以生成 next_chunk_ids。"
                    "每个知识点最多给 2 个 prerequisite 和 2 个 next，保持高置信。"
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
            ][:2]
            valid_next = [
                cid
                for cid in relation.get("next_chunk_ids", [])
                if isinstance(cid, str) and cid in by_id and cid != chunk_id
            ][:2]
            by_id[chunk_id]["metadata"]["prerequisite_node_ids"] = valid_pre
            by_id[chunk_id]["metadata"]["next_node_ids"] = valid_next
    return chunks


def add_rule_sequence_relations(chunks: list[dict[str, Any]]) -> int:
    """Add conservative next relations by page/order when no LLM relation exists."""

    relation_count = sum(
        len(chunk.get("metadata", {}).get("prerequisite_node_ids", []) or [])
        + len(chunk.get("metadata", {}).get("next_node_ids", []) or [])
        for chunk in chunks
    )
    if relation_count:
        return 0

    def sort_key(chunk: dict[str, Any]) -> tuple[int, int, str]:
        pages = chunk.get("metadata", {}).get("pages", []) or [999999]
        first_page = min(page for page in pages if isinstance(page, int)) if pages else 999999
        index = chunk.get("metadata", {}).get("chunk_index", 0)
        return (first_page, int(index or 0), str(chunk.get("chunk_id")))

    ordered = sorted(chunks, key=sort_key)
    added = 0
    for previous, current in zip(ordered, ordered[1:]):
        previous.setdefault("metadata", {}).setdefault("next_node_ids", []).append(current["chunk_id"])
        current.setdefault("metadata", {}).setdefault("prerequisite_node_ids", []).append(previous["chunk_id"])
        previous["metadata"]["relation_source"] = "rule_sequence"
        current["metadata"]["relation_source"] = "rule_sequence"
        added += 2
    return added


def attach_tree_chunk_counts(nodes: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        node_id = chunk.get("node_id")
        counts[node_id] = counts.get(node_id, 0) + 1
    result = []
    for node in nodes:
        item = dict(node)
        item["chunk_count"] = counts.get(node.get("node_id"), 0)
        result.append(item)
    return result


def build_edges(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    valid_chunk_ids = {chunk.get("chunk_id") for chunk in chunks}
    for chunk in chunks:
        source = chunk["chunk_id"]
        metadata = chunk.get("metadata", {})
        for target in metadata.get("prerequisite_node_ids", []) or []:
            if target in valid_chunk_ids:
                edges.append({"source": target, "target": source, "type": "prerequisite"})
        for target in metadata.get("next_node_ids", []) or []:
            if target in valid_chunk_ids:
                edges.append({"source": source, "target": target, "type": "next"})
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["type"])
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


def prune_outline_nodes(nodes: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {node.get("node_id"): node for node in nodes}
    keep_ids: set[str] = set()
    for chunk in chunks:
        node_id = chunk.get("node_id")
        while node_id and node_id in by_id:
            keep_ids.add(node_id)
            node_id = by_id[node_id].get("parent_id")
    result = []
    for node in nodes:
        if node.get("node_id") in keep_ids:
            result.append(node)
    return result


def build_knowledge_tree(pdf_json: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    pruned_nodes = prune_outline_nodes(pdf_json.get("outline_nodes", []), chunks)
    nodes = attach_tree_chunk_counts(pruned_nodes, chunks)
    chunk_nodes = [
        {
            "chunk_id": chunk["chunk_id"],
            "parent_node_id": chunk["node_id"],
            "title": chunk.get("metadata", {}).get("knowledge_point")
            or chunk.get("metadata", {}).get("section_title")
            or "知识点",
            "pages": chunk.get("metadata", {}).get("pages", []),
            "method": chunk.get("metadata", {}).get("chunk_method", "rule"),
            "char_count": len(chunk.get("content_text", "")),
        }
        for chunk in chunks
    ]
    return {
        "stage": "knowledge_tree",
        "source_file": pdf_json.get("source_file", ""),
        "course": pdf_json.get("course", "软件工程"),
        "outline_nodes": nodes,
        "knowledge_points": chunk_nodes,
        "relations": build_edges(chunks),
        "stats": {
            "outline_node_count": len(nodes),
            "knowledge_point_count": len(chunk_nodes),
            "relation_count": len(build_edges(chunks)),
        },
    }


def mermaid_label(text: str, limit: int = 36) -> str:
    safe = str(text).replace("\n", " ").replace("(", "（").replace(")", "）")
    return safe[:limit] + ("..." if len(safe) > limit else "")


def write_mermaid_mindmap(tree: dict[str, Any], output_path: Path) -> None:
    children: dict[str | None, list[dict[str, Any]]] = {}
    for node in tree["outline_nodes"]:
        children.setdefault(node.get("parent_id"), []).append(node)

    lines = ["mindmap"]

    def walk(node: dict[str, Any], depth: int) -> None:
        indent = "  " * depth
        count = node.get("chunk_count", 0)
        suffix = f" [{count}]" if count else ""
        lines.append(f"{indent}{mermaid_label(node.get('title', '知识点'))}{suffix}")
        for child in children.get(node.get("node_id"), []):
            walk(child, depth + 1)

    roots = children.get(None) or tree["outline_nodes"][:1]
    for root in roots:
        walk(root, 1)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_paths(input_path: Path, output_dir: str) -> tuple[Path, Path, Path]:
    base_dir = Path(output_dir) if output_dir else input_path.parent
    stem = input_path.stem.removesuffix("_pdf")
    return (
        base_dir / f"{stem}_semantic.json",
        base_dir / f"{stem}_knowledge_tree.json",
        base_dir / f"{stem}_knowledge_tree.mmd",
    )


# The original project was sometimes edited under a mismatched console encoding,
# so keep a clean UTF-8 rule set here. These definitions intentionally override
# the earlier filter/merge helpers and make the command-line pipeline stricter.
STRICT_NOISE_TITLE_PATTERNS = [
    r"^\s*课堂",
    r"^\s*课后",
    r"^\s*作业",
    r"^\s*练习",
    r"^\s*习题",
    r"^\s*测试",
    r"^\s*思考题",
    r"^\s*讨论",
    r"^\s*问题",
    r"^\s*问答",
    r"^\s*案例\s*[:：]?\s*$",
    r"^\s*学以致用",
    r"^\s*本章小结",
    r"^\s*小结\s*$",
    r"^\s*目录\s*$",
    r"^\s*参考文献",
    r"^\s*拓展阅读",
]
STRICT_NOISE_TEXT_PATTERNS = [
    r"^\s*(请问|问题|讨论|思考|练习|作业|要求)\s*[:：]",
    r"^\s*\d+\s*[\.、)]\s*.*(请选择|请回答|判断|填空|简答|计算|说明)",
    r"(课堂练习|课后练习|课后习题|习题|作业|思考题|讨论题)",
    r"(选择题|判断题|填空题|简答题|问答题|案例题)",
]
STRICT_GENERIC_SHORT_TITLES = {"软件工程", "高级软件工程", "SDLC", "C", "开始", "结束"}


def normalize_title_key(title: str) -> str:
    text = normalize_text(title).lower()
    text = re.sub(r"^\s*第[一二三四五六七八九十百千万零〇两\d]+[章节篇]\s*", "", text)
    text = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", text)
    text = re.sub(r"^\s*[(（]?\d+[)）、.]\s*", "", text)
    text = re.sub(r"[\s:：，,。；;、()（）\-_/\[\]【】]+", "", text)
    return text


def looks_like_toc_or_fragment(text: str) -> bool:
    compact = normalize_text(text)
    if not compact:
        return True
    if len(compact) < 18:
        return True
    numbered_hits = len(re.findall(r"\d+\.\d+", compact))
    dot_page_hits = len(re.findall(r"\.{2,}\s*\d{1,4}", compact))
    if len(compact) < 180 and (numbered_hits >= 5 or dot_page_hits >= 3):
        return True
    if len(compact) < 160 and re.search(r"(目录|contents|table of contents)", compact, re.I):
        return True
    return False


def is_exercise_like_text(text: str) -> bool:
    compact = normalize_text(text)
    if not compact:
        return True
    hits = sum(1 for pattern in STRICT_NOISE_TEXT_PATTERNS if re.search(pattern, compact))
    if hits >= 1 and len(compact) < 900:
        return True
    question_marks = compact.count("？") + compact.count("?")
    if question_marks >= 2 and re.search(r"(请问|为什么|如何|哪些|是否|分别|采用什么)", compact):
        return True
    return False


def is_non_knowledge_chunk(chunk: dict[str, Any]) -> tuple[bool, str]:
    metadata = chunk.get("metadata", {})
    title = str(metadata.get("knowledge_point") or metadata.get("section_title") or "").strip()
    path = [str(item).strip() for item in metadata.get("section_path", []) or []]
    text = str(chunk.get("content_text") or "")
    if any(re.search(pattern, title) for pattern in STRICT_NOISE_TITLE_PATTERNS):
        return True, "exercise_or_admin_title"
    if any(
        any(re.search(pattern, part) for pattern in STRICT_NOISE_TITLE_PATTERNS)
        for part in path
    ):
        return True, "exercise_or_admin_path"
    if title in STRICT_GENERIC_SHORT_TITLES and looks_like_toc_or_fragment(text):
        return True, "generic_fragment"
    if looks_like_toc_or_fragment(text):
        return True, "toc_or_fragment"
    if is_exercise_like_text(text):
        return True, "exercise_like_text"
    return False, ""


def filter_non_knowledge_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for chunk in chunks:
        should_remove, reason = is_non_knowledge_chunk(chunk)
        if should_remove:
            removed.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "title": chunk.get("metadata", {}).get("knowledge_point")
                    or chunk.get("metadata", {}).get("section_title"),
                    "reason": reason,
                    "pages": chunk.get("metadata", {}).get("pages", []),
                    "text_preview": str(chunk.get("content_text") or "")[:180],
                }
            )
            continue
        kept.append(chunk)
    return kept, removed


def merge_duplicate_chunks(chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        title = str(metadata.get("knowledge_point") or metadata.get("section_title") or "知识点")
        key = normalize_title_key(title) or str(chunk.get("chunk_id"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(chunk)

    merged: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for key in order:
        items = groups[key]
        if len(items) == 1:
            merged.append(items[0])
            continue
        base = json.loads(json.dumps(items[0], ensure_ascii=False))
        titles = [
            str(item.get("metadata", {}).get("knowledge_point") or item.get("metadata", {}).get("section_title") or "")
            for item in items
        ]
        title = CounterTitle.pick(titles)
        pages = sorted(
            {
                page
                for item in items
                for page in item.get("metadata", {}).get("pages", [])
                if isinstance(page, int)
            }
        )
        images: list[dict[str, Any]] = []
        seen_images: set[str] = set()
        texts: list[str] = []
        seen_texts: set[str] = set()
        for item in items:
            text = normalize_text(str(item.get("content_text") or ""))
            text_key = re.sub(r"\s+", "", text)
            if text and text_key not in seen_texts:
                seen_texts.add(text_key)
                texts.append(text)
            for image in item.get("metadata", {}).get("images", []) or []:
                image_key = str(image.get("image_id") or image.get("path") or image)
                if image_key not in seen_images:
                    seen_images.add(image_key)
                    images.append(image)
        merged_id = stable_id("merged", key, "|".join(item.get("chunk_id", "") for item in items))
        base["chunk_id"] = merged_id
        base["content_text"] = "\n\n".join(texts)
        base["metadata"]["knowledge_point"] = title
        base["metadata"]["pages"] = pages
        base["metadata"]["images"] = images
        base["metadata"]["chunk_method"] = "merged"
        base["metadata"]["merged_from_chunk_ids"] = [item.get("chunk_id") for item in items]
        base["metadata"]["prerequisite_node_ids"] = []
        base["metadata"]["next_node_ids"] = []
        merged.append(base)
        reports.append({"title": title, "merged_count": len(items), "merged_chunk_id": merged_id})
    return merged, reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate semantic chunks and a knowledge tree from PDF JSON.")
    parser.add_argument("--input-json", required=True, help="JSON from pdf_to_json.py")
    parser.add_argument("--output-dir", default="", help="Output directory; default: input JSON directory")
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--use-llm-boundaries", action="store_true")
    parser.add_argument("--generate-relations", action="store_true")
    parser.add_argument("--no-filter-non-knowledge", action="store_true", help="Keep classroom activities, TOC fragments, and other noisy chunks.")
    parser.add_argument("--no-merge-duplicates", action="store_true", help="Do not merge chunks with the same normalized knowledge-point title.")
    parser.add_argument("--no-rule-relation-fallback", action="store_true", help="Do not add sequential rule relations when LLM relations are empty.")
    parser.add_argument("--max-llm-chunks", type=int, default=0, help="Limit LLM boundary calls; 0 means all")
    parser.add_argument("--relation-window-size", type=int, default=10)
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-model", default="Qwen3.6-35B-A3B")
    parser.add_argument("--api-timeout", type=int, default=60)
    parser.add_argument("--api-retries", type=int, default=3)
    parser.add_argument("--api-retry-delay", type=float, default=3.0)
    parser.add_argument("--api-delay", type=float, default=1.0)
    parser.add_argument(
        "--disable-response-format",
        action="store_true",
        help="Use this if the model endpoint rejects OpenAI response_format.",
    )
    parser.add_argument(
        "--disable-ssl-verify",
        action="store_true",
        help="Disable TLS certificate verification for troublesome MaaS gateways.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_json)
    pdf_json = load_pdf_json(input_path)
    chunks = json.loads(json.dumps(pdf_json["rule_chunks"], ensure_ascii=False))

    llm = None
    if args.use_llm_boundaries or args.generate_relations:
        llm = build_llm(args)

    if args.use_llm_boundaries:
        chunks = refine_chunks_with_llm(
            chunks,
            llm,  # type: ignore[arg-type]
            max_chars=args.max_chars,
            max_chunks=args.max_llm_chunks,
        )

    filtered_out: list[dict[str, Any]] = []
    merge_report: list[dict[str, Any]] = []
    if not args.no_filter_non_knowledge:
        chunks, filtered_out = filter_non_knowledge_chunks(chunks)

    if not args.no_merge_duplicates:
        chunks, merge_report = merge_duplicate_chunks(chunks)

    for chunk in chunks:
        chunk.setdefault("metadata", {})["prerequisite_node_ids"] = []
        chunk.setdefault("metadata", {})["next_node_ids"] = []

    if args.generate_relations:
        chunks = generate_relations_with_llm(
            chunks,
            llm,  # type: ignore[arg-type]
            window_size=args.relation_window_size,
        )

    rule_relation_added = 0
    if not args.no_rule_relation_fallback:
        rule_relation_added = add_rule_sequence_relations(chunks)

    semantic_path, tree_path, mermaid_path = output_paths(input_path, args.output_dir)
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_payload = make_payload_dict(
        Path(pdf_json.get("source_file", input_path)),
        pdf_json.get("course", "软件工程"),
        int(pdf_json.get("max_chars", args.max_chars) or args.max_chars),
        int(pdf_json.get("overlap", 0) or 0),
        pdf_json.get("outline_nodes", []),
        chunks,
    )
    semantic_payload["stage"] = "semantic_slice"
    semantic_payload["llm"] = {
        "used_boundaries": bool(args.use_llm_boundaries),
        "generated_relations": bool(args.generate_relations),
        "model": args.llm_model if llm else "",
        "base_url": args.llm_base_url if llm else "",
    }
    semantic_payload["cleaning"] = {
        "filtered_non_knowledge_count": len(filtered_out),
        "filtered_non_knowledge_samples": filtered_out[:80],
        "merged_duplicate_group_count": len(merge_report),
        "merged_duplicate_samples": merge_report[:80],
        "rule_relation_fallback_edges_added": rule_relation_added,
    }
    semantic_path.write_text(json.dumps(semantic_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tree = build_knowledge_tree(pdf_json, chunks)
    tree_path.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    write_mermaid_mindmap(tree, mermaid_path)

    print(f"Semantic chunks exported: {semantic_path}")
    print(f"Knowledge tree exported: {tree_path}")
    print(f"Mermaid mindmap exported: {mermaid_path}")
    print(
        f"Knowledge points: {tree['stats']['knowledge_point_count']}; "
        f"Relations: {tree['stats']['relation_count']}"
    )
    print(
        f"Filtered non-knowledge chunks: {len(filtered_out)}; "
        f"Merged duplicate groups: {len(merge_report)}; "
        f"Rule fallback relation endpoints added: {rule_relation_added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
