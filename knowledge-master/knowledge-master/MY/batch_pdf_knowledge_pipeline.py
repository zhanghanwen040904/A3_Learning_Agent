r"""Batch convert PDFs to knowledge-only JSON, semantic chunks, and JSON trees.

This script is file-only. It does not write MySQL.

Example:
    python MY/batch_pdf_knowledge_pipeline.py ^
      --input-dir "C:\Users\ASUS\Desktop\新建文件夹 (2)" ^
      --output-dir "E:\知识问答\MY\batch_outputs" ^
      --course "软件工程"
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

try:
    import fitz
except ImportError as exc:
    raise SystemExit("Missing dependency: PyMuPDF. Run: python -m pip install PyMuPDF") from exc

from ingest_pdf_to_mysql import build_payload, make_payload_dict, normalize_text, parse_pdf
from pdf_to_json import serialize_sections
from semantic_slice_tree import (
    add_rule_sequence_relations,
    build_knowledge_tree,
    build_llm,
    filter_non_knowledge_chunks,
    generate_relations_with_llm,
    merge_duplicate_chunks,
    refine_chunks_with_llm,
    write_mermaid_mindmap,
)


def safe_stem(path: Path) -> str:
    return "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in path.stem).strip() or "book"


def find_pdfs(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path for path in input_dir.glob(pattern) if path.is_file())


def image_rule_class(image: dict[str, Any]) -> str:
    """Cheap pre-filter before sending images to a vision model."""

    width = int(image.get("width") or 0)
    height = int(image.get("height") or 0)
    file_size = int(image.get("file_size") or 0)
    area = width * height
    if width <= 90 or height <= 90 or area < 6000 or file_size < 1500:
        return "tiny_icon_or_fragment"
    if file_size < 6000 and area < 50000:
        return "small_decoration_likely"
    if file_size >= 20000 and area >= 40000:
        return "vision_candidate"
    if file_size >= 12000 and area >= 80000:
        return "vision_candidate"
    return "uncertain_or_decoration"


def image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def candidate_titles_for_image(image: dict[str, Any], chunks: list[dict[str, Any]], limit: int = 16) -> list[dict[str, Any]]:
    page = image.get("page")
    candidates: list[dict[str, Any]] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        pages = metadata.get("pages", []) or []
        if page in pages:
            candidates.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "title": metadata.get("knowledge_point") or metadata.get("section_title"),
                    "pages": pages,
                    "text_preview": str(chunk.get("content_text") or "")[:260],
                }
            )
    return candidates[:limit]


def complete_image_json(
    llm: Any,
    *,
    system_prompt: str,
    text_prompt: str,
    image_path: Path,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": llm.config.model,
        "temperature": 0.05,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                ],
            },
        ],
    }
    if getattr(llm, "use_response_format", False):
        payload["response_format"] = {"type": "json_object"}
    result = llm.post_json(payload)
    content = result["choices"][0]["message"]["content"]
    from ingest_pdf_to_mysql import extract_json_object

    return extract_json_object(content)


def filter_images_with_llm(
    images: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    llm: Any,
    *,
    max_images: int,
    keep_rule_candidates_only: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use a multimodal LLM to keep only knowledge-related teaching images."""

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    system_prompt = (
        "你是软件工程课程教材图片筛选助手。请判断图片是否是有教学价值的知识图。"
        "只输出 JSON，不要解释。不要把 PPT 装饰、logo、圆点、渐变条、页眉页脚、空白背景、小图标当作知识图。"
    )
    processed = 0
    for image in images:
        rule_class = image_rule_class(image)
        image["rule_class"] = rule_class
        if keep_rule_candidates_only and rule_class not in {"vision_candidate"}:
            item = dict(image)
            item["is_knowledge_image"] = False
            item["reject_reason"] = rule_class
            item["llm_checked"] = False
            rejected.append(item)
            continue
        if max_images > 0 and processed >= max_images:
            item = dict(image)
            item["is_knowledge_image"] = False
            item["reject_reason"] = "over_max_llm_images"
            item["llm_checked"] = False
            rejected.append(item)
            continue
        image_path = Path(str(image.get("absolute_path") or ""))
        if not image_path.exists():
            item = dict(image)
            item["is_knowledge_image"] = False
            item["reject_reason"] = "image_file_missing"
            item["llm_checked"] = False
            rejected.append(item)
            continue

        candidates = candidate_titles_for_image(image, chunks)
        text_prompt = json.dumps(
            {
                "instruction": (
                    "判断这张图片是否应该作为软件工程课程知识点配图保留。"
                    "如果是流程图、ER图、数据流图、结构图、表格、算法图、测试流程图、模型图、界面示例、代码/伪代码示例，可保留。"
                    "如果只是 PPT 模板、学校 logo、圆点装饰、渐变条、小图标、页脚页眉、无正文意义的背景，请丢弃。"
                    "只能从 candidate_knowledge_points 中选择最相关的 chunk_id，最多 4 个。"
                ),
                "required_json_schema": {
                    "is_knowledge_image": True,
                    "image_type": "diagram|flowchart|table|screenshot|code|formula|concept_map|other|decoration",
                    "caption": "一句话说明图片内容",
                    "related_chunk_ids": ["existing chunk_id"],
                    "confidence": 0.0,
                    "reject_reason": "",
                },
                "image": {
                    "image_id": image.get("image_id"),
                    "page": image.get("page"),
                    "width": image.get("width"),
                    "height": image.get("height"),
                    "file_size": image.get("file_size"),
                    "rule_class": rule_class,
                },
                "candidate_knowledge_points": candidates,
            },
            ensure_ascii=False,
        )
        try:
            result = complete_image_json(
                llm,
                system_prompt=system_prompt,
                text_prompt=text_prompt,
                image_path=image_path,
            )
            processed += 1
            candidate_ids = {item.get("chunk_id") for item in candidates}
            related = [
                cid
                for cid in result.get("related_chunk_ids", [])
                if isinstance(cid, str) and cid in candidate_ids
            ][:4]
            item = dict(image)
            item["llm_checked"] = True
            item["is_knowledge_image"] = bool(result.get("is_knowledge_image")) and bool(related)
            item["image_type"] = str(result.get("image_type") or "")
            item["caption"] = str(result.get("caption") or "")
            item["related_chunk_ids"] = related
            item["confidence"] = float(result.get("confidence") or 0.0)
            item["reject_reason"] = str(result.get("reject_reason") or "")
            if item["is_knowledge_image"] and item["confidence"] >= 0.45:
                kept.append(item)
            else:
                if not item["reject_reason"]:
                    item["reject_reason"] = "llm_rejected_or_low_confidence"
                rejected.append(item)
        except Exception as exc:
            item = dict(image)
            item["llm_checked"] = False
            item["is_knowledge_image"] = False
            item["reject_reason"] = f"llm_error: {exc}"
            rejected.append(item)
    return kept, rejected


def extract_pdf_images(pdf_path: Path, image_root: Path, output_root: Path) -> list[dict[str, Any]]:
    """Extract page images and return JSON metadata.

    Images are linked to chunks later by page number. This keeps knowledge-point
    diagrams and flowcharts available without storing binary data inside JSON.
    """

    image_dir = image_root / safe_stem(pdf_path)
    image_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            page = doc.load_page(page_index)
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = int(image_info[0])
                key = (page_number, xref)
                if key in seen:
                    continue
                seen.add(key)
                image = doc.extract_image(xref)
                image_bytes = image.get("image")
                if not image_bytes:
                    continue
                ext = image.get("ext") or "png"
                file_name = f"page_{page_number:03d}_img_{image_index:02d}.{ext}"
                file_path = image_dir / file_name
                file_path.write_bytes(image_bytes)
                try:
                    relative_path = str(file_path.relative_to(output_root))
                except ValueError:
                    relative_path = str(file_path)
                file_size = file_path.stat().st_size
                extracted.append(
                    {
                        "image_id": f"{safe_stem(pdf_path)}_p{page_number:03d}_i{image_index:02d}",
                        "page": page_number,
                        "file_name": file_name,
                        "path": relative_path.replace("\\", "/"),
                        "absolute_path": str(file_path),
                        "width": int(image.get("width") or 0),
                        "height": int(image.get("height") or 0),
                        "file_size": file_size,
                        "ext": ext,
                        "xref": xref,
                    }
                )
    finally:
        doc.close()
    return extracted


def attach_images_to_chunks(chunks: list[dict[str, Any]], images: list[dict[str, Any]]) -> None:
    llm_related_images = [image for image in images if image.get("related_chunk_ids")]
    if llm_related_images:
        by_chunk_id: dict[str, list[dict[str, Any]]] = {}
        for image in llm_related_images:
            for chunk_id in image.get("related_chunk_ids", []) or []:
                if isinstance(chunk_id, str):
                    by_chunk_id.setdefault(chunk_id, []).append(image)
        for chunk in chunks:
            chunk.setdefault("metadata", {})["images"] = by_chunk_id.get(str(chunk.get("chunk_id")), [])
        return

    images_by_page: dict[int, list[dict[str, Any]]] = {}
    for image in images:
        page = image.get("page")
        if isinstance(page, int):
            images_by_page.setdefault(page, []).append(image)
    for chunk in chunks:
        pages = chunk.get("metadata", {}).get("pages", []) or []
        attached: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in pages:
            for image in images_by_page.get(page, []):
                image_id = str(image.get("image_id"))
                if image_id not in seen:
                    seen.add(image_id)
                    attached.append(image)
        chunk.setdefault("metadata", {})["images"] = attached


def add_images_to_tree(tree: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
    by_id = {chunk.get("chunk_id"): chunk for chunk in chunks}
    for point in tree.get("knowledge_points", []):
        chunk = by_id.get(point.get("chunk_id"))
        if chunk:
            point["images"] = chunk.get("metadata", {}).get("images", [])


def process_pdf(pdf_path: Path, args: argparse.Namespace, llm: Any | None) -> dict[str, Any]:
    stem = safe_stem(pdf_path)
    pdf_json_dir = Path(args.output_dir) / "pdf_json"
    semantic_dir = Path(args.output_dir) / "semantic_json"
    tree_dir = Path(args.output_dir) / "knowledge_tree_json"
    image_root = Path(args.output_dir) / "images"
    for directory in (pdf_json_dir, semantic_dir, tree_dir, image_root):
        directory.mkdir(parents=True, exist_ok=True)

    sections = parse_pdf(pdf_path, args.course, skip_toc=not args.no_skip_toc)
    raw_payload = build_payload(
        pdf_path,
        args.course,
        sections,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    images = extract_pdf_images(pdf_path, image_root, Path(args.output_dir))

    chunks = json.loads(json.dumps(raw_payload["knowledge_chunks"], ensure_ascii=False))
    filtered_once: list[dict[str, Any]] = []
    merged_once: list[dict[str, Any]] = []
    chunks, filtered_once = filter_non_knowledge_chunks(chunks)
    chunks, merged_once = merge_duplicate_chunks(chunks)
    if not args.use_llm_image_filter:
        attach_images_to_chunks(chunks, images)

    pdf_json = {
        "stage": "pdf_to_knowledge_json",
        "source_file": str(pdf_path),
        "course": args.course,
        "sections": serialize_sections(sections),
        "outline_nodes": raw_payload["outline_nodes"],
        "rule_chunks": chunks,
        "images": images,
        "cleaning": {
            "filtered_non_knowledge_count": len(filtered_once),
            "filtered_non_knowledge_samples": filtered_once[:80],
            "merged_duplicate_group_count": len(merged_once),
            "merged_duplicate_samples": merged_once[:80],
        },
        "stats": {
            **raw_payload["stats"],
            "section_count": len(sections),
            "paragraph_count": sum(len(section.paragraphs) for section in sections),
            "knowledge_only_chunk_count": len(chunks),
            "image_count": len(images),
        },
    }
    pdf_json_path = pdf_json_dir / f"{stem}_knowledge.json"

    semantic_chunks = json.loads(json.dumps(chunks, ensure_ascii=False))
    if args.use_llm_boundaries:
        semantic_chunks = refine_chunks_with_llm(
            semantic_chunks,
            llm,
            max_chars=args.max_chars,
            max_chunks=args.max_llm_chunks,
        )
    filtered_twice: list[dict[str, Any]] = []
    merged_twice: list[dict[str, Any]] = []
    semantic_chunks, filtered_twice = filter_non_knowledge_chunks(semantic_chunks)
    semantic_chunks, merged_twice = merge_duplicate_chunks(semantic_chunks)

    rejected_images: list[dict[str, Any]] = []
    if args.use_llm_image_filter:
        images, rejected_images = filter_images_with_llm(
            images,
            semantic_chunks,
            llm,
            max_images=args.max_llm_images,
            keep_rule_candidates_only=not args.llm_check_all_images,
        )
        if args.delete_rejected_images:
            for image in rejected_images:
                path = Path(str(image.get("absolute_path") or ""))
                if path.exists():
                    path.unlink()
        attach_images_to_chunks(chunks, images)

    attach_images_to_chunks(semantic_chunks, images)
    for chunk in semantic_chunks:
        chunk.setdefault("metadata", {})["prerequisite_node_ids"] = []
        chunk.setdefault("metadata", {})["next_node_ids"] = []

    if args.generate_relations:
        semantic_chunks = generate_relations_with_llm(
            semantic_chunks,
            llm,
            window_size=args.relation_window_size,
        )
    rule_relation_added = 0
    if not args.no_rule_relation_fallback:
        rule_relation_added = add_rule_sequence_relations(semantic_chunks)

    pdf_json["rule_chunks"] = chunks
    pdf_json["images"] = images
    pdf_json["rejected_images"] = rejected_images[:500]
    pdf_json["stats"]["image_count"] = len(images)
    pdf_json["stats"]["rejected_image_count"] = len(rejected_images)
    pdf_json["image_filter"] = {
        "used_llm": bool(args.use_llm_image_filter),
        "model": args.llm_model if args.use_llm_image_filter else "",
        "deleted_rejected_images": bool(args.delete_rejected_images),
    }
    pdf_json_path.write_text(json.dumps(pdf_json, ensure_ascii=False, indent=2), encoding="utf-8")

    semantic_payload = make_payload_dict(
        pdf_path,
        args.course,
        args.max_chars,
        args.overlap,
        pdf_json["outline_nodes"],
        semantic_chunks,
    )
    semantic_payload["stage"] = "semantic_slice"
    semantic_payload["source_pdf_json"] = str(pdf_json_path)
    semantic_payload["images"] = images
    semantic_payload["rejected_images"] = rejected_images[:500]
    semantic_payload["cleaning"] = {
        "filtered_non_knowledge_count": len(filtered_once) + len(filtered_twice),
        "filtered_non_knowledge_samples": (filtered_once + filtered_twice)[:120],
        "merged_duplicate_group_count": len(merged_once) + len(merged_twice),
        "merged_duplicate_samples": (merged_once + merged_twice)[:120],
        "rule_relation_fallback_edges_added": rule_relation_added,
        "rejected_image_count": len(rejected_images),
    }
    semantic_payload["llm"] = {
        "used_boundaries": bool(args.use_llm_boundaries),
        "generated_relations": bool(args.generate_relations),
        "used_image_filter": bool(args.use_llm_image_filter),
        "model": args.llm_model if llm else "",
        "base_url": args.llm_base_url if llm else "",
    }
    semantic_path = semantic_dir / f"{stem}_semantic.json"
    semantic_path.write_text(json.dumps(semantic_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tree = build_knowledge_tree(pdf_json, semantic_chunks)
    add_images_to_tree(tree, semantic_chunks)
    tree["source_pdf_json"] = str(pdf_json_path)
    tree["source_semantic_json"] = str(semantic_path)
    tree["images"] = images
    tree["rejected_image_count"] = len(rejected_images)
    tree["image_filter"] = {
        "used_llm": bool(args.use_llm_image_filter),
        "model": args.llm_model if args.use_llm_image_filter else "",
    }
    tree_path = tree_dir / f"{stem}_knowledge_tree.json"
    tree_path.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    mermaid_path = tree_dir / f"{stem}_knowledge_tree.mmd"
    write_mermaid_mindmap(tree, mermaid_path)

    return {
        "pdf": str(pdf_path),
        "pdf_json": str(pdf_json_path),
        "semantic_json": str(semantic_path),
        "knowledge_tree_json": str(tree_path),
        "mermaid": str(mermaid_path),
        "knowledge_points": tree["stats"]["knowledge_point_count"],
        "relations": tree["stats"]["relation_count"],
        "images": len(images),
        "rejected_images": len(rejected_images),
        "filtered": len(filtered_once) + len(filtered_twice),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch PDF knowledge-only JSON and knowledge-tree pipeline.")
    parser.add_argument("--input-dir", required=True, help="Folder containing PDF files")
    parser.add_argument("--output-dir", default="batch_outputs", help="Output folder")
    parser.add_argument("--course", default="软件工程")
    parser.add_argument("--recursive", action="store_true", help="Scan PDFs recursively")
    parser.add_argument("--max-chars", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--no-skip-toc", action="store_true")
    parser.add_argument("--use-llm-boundaries", action="store_true")
    parser.add_argument("--generate-relations", action="store_true")
    parser.add_argument("--use-llm-image-filter", action="store_true", help="Use a multimodal LLM to keep and link knowledge-related images.")
    parser.add_argument("--llm-check-all-images", action="store_true", help="Send all extracted images to the LLM instead of only rule-selected candidates.")
    parser.add_argument("--delete-rejected-images", action="store_true", help="Delete images rejected by the LLM or rule pre-filter.")
    parser.add_argument("--max-llm-images", type=int, default=0, help="Limit LLM image checks per PDF; 0 means all candidates.")
    parser.add_argument("--no-rule-relation-fallback", action="store_true")
    parser.add_argument("--max-llm-chunks", type=int, default=0)
    parser.add_argument("--relation-window-size", type=int, default=10)
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--llm-api-key", default="")
    parser.add_argument("--llm-model", default="xopqwen35v35b")
    parser.add_argument("--api-timeout", type=int, default=120)
    parser.add_argument("--api-retries", type=int, default=3)
    parser.add_argument("--api-retry-delay", type=float, default=3.0)
    parser.add_argument("--api-delay", type=float, default=1.5)
    parser.add_argument("--disable-response-format", action="store_true")
    parser.add_argument("--disable-ssl-verify", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input folder not found: {input_dir}")
    pdfs = find_pdfs(input_dir, args.recursive)
    if not pdfs:
        raise SystemExit(f"No PDF files found in: {input_dir}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    llm = build_llm(args) if args.use_llm_boundaries or args.generate_relations or args.use_llm_image_filter else None

    summary: list[dict[str, Any]] = []
    for index, pdf_path in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] Processing: {pdf_path}")
        try:
            item = process_pdf(pdf_path, args, llm)
            summary.append(item)
            print(
                "  OK: "
                f"knowledge_points={item['knowledge_points']}, "
                f"relations={item['relations']}, "
                f"images={item['images']}, "
                f"rejected_images={item.get('rejected_images', 0)}, "
                f"filtered={item['filtered']}"
            )
        except Exception as exc:  # keep batch processing moving
            failed = {"pdf": str(pdf_path), "error": repr(exc)}
            summary.append(failed)
            print(f"  FAILED: {exc}", file=sys.stderr)

    summary_path = output_dir / "batch_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Batch summary exported: {summary_path}")
    print(f"Processed PDFs: {len(pdfs)}; Success: {sum(1 for item in summary if 'error' not in item)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
