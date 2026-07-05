"""Convert a textbook PDF to structured JSON for later semantic slicing.

This script is intentionally file-only: it does not call an LLM and does not
write MySQL. It reuses the robust PDF parsing utilities from
``MY/ingest_pdf_to_mysql.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ingest_pdf_to_mysql import Section, build_payload, parse_pdf


def serialize_sections(sections: list[Section]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": section.node_id,
            "parent_id": section.parent_id,
            "title": section.title,
            "level": section.level,
            "chapter_id": section.chapter_id,
            "start_page": section.start_page,
            "path": section.path,
            "paragraphs": section.paragraphs,
        }
        for section in sections
    ]


def default_output_path(pdf_path: Path) -> Path:
    return pdf_path.with_name(f"{pdf_path.stem}_pdf.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert PDF to structured JSON.")
    parser.add_argument("--pdf", required=True, help="PDF file path")
    parser.add_argument("--course", default="软件工程", help="Course/book name")
    parser.add_argument("--output", default="", help="Output JSON path; default: same directory as PDF")
    parser.add_argument("--max-chars", type=int, default=800, help="Rule chunk size used for preview chunks")
    parser.add_argument("--overlap", type=int, default=100, help="Rule chunk overlap used for preview chunks")
    parser.add_argument("--no-skip-toc", action="store_true", help="Do not skip table-of-contents-like pages")
    parser.add_argument("--print-samples", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    sections = parse_pdf(pdf_path, args.course, skip_toc=not args.no_skip_toc)
    preview_payload = build_payload(
        pdf_path,
        args.course,
        sections,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    payload = {
        "stage": "pdf_to_json",
        "source_file": str(pdf_path),
        "course": args.course,
        "sections": serialize_sections(sections),
        "outline_nodes": preview_payload["outline_nodes"],
        "rule_chunks": preview_payload["knowledge_chunks"],
        "stats": {
            **preview_payload["stats"],
            "section_count": len(sections),
            "paragraph_count": sum(len(section.paragraphs) for section in sections),
        },
    }

    output_path = Path(args.output) if args.output else default_output_path(pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"PDF JSON exported: {output_path}")
    print(
        f"Sections: {payload['stats']['section_count']}; "
        f"Paragraphs: {payload['stats']['paragraph_count']}; "
        f"Rule chunks: {payload['stats']['chunk_count']}"
    )
    for chunk in payload["rule_chunks"][: max(args.print_samples, 0)]:
        text = chunk["content_text"].replace("\n", " ")
        print(
            "\n--- sample rule chunk ---\n"
            f"id: {chunk['chunk_id']}\n"
            f"path: {' > '.join(chunk['metadata'].get('section_path', []))}\n"
            f"chars: {len(chunk['content_text'])}\n"
            f"text: {text[:300]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
