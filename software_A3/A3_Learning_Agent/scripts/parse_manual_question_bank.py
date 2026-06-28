import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_ROOT = PROJECT_ROOT / "rag_data" / "manual_question_bank" / "pdf_source"
OUTPUT_PATH = PROJECT_ROOT / "rag_data" / "manual_question_bank" / "manual_question_bank_draft.json"


SECTION_PATTERN = re.compile(
    r"([一二三四五六七八九十]+)\s*[.．、]\s*(单选题|多选题|判断题|填空题|简答题|综合题|问答题|分析题)\s*[（(]\s*共?\s*(\d+)\s*题\s*[)）]"
)
QUESTION_START_PATTERN = re.compile(r"(?m)^\s*(\d+)\.\s*(?:\((单选题|多选题|判断题|填空题|简答题|问答题|分析题)\))?\s*$")
QUESTION_START_INLINE_PATTERN = re.compile(
    r"(?m)^\s*(\d+)\.\s*(?:\((单选题|多选题|判断题|填空题|简答题|问答题|分析题)\))?\s*"
)
OPTION_PATTERN = re.compile(r"(?m)^\s*([A-H])\.\s*(.+?)\s*$")
ANSWER_PATTERN = re.compile(r"正确答.{0,2}:\s*([A-H]+)\s*:?(.*?)(?:\s*;\s*)?$", re.S)


@dataclass
class ParsedQuestion:
    source_pdf: str
    chapter: str
    section_title: str
    section_order: str
    section_declared_count: int
    question_no: int
    question_type: str
    prompt: str
    options: List[dict]
    answer: str
    answer_text: str
    raw_block: str


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\u3000", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chapter_from_filename(name: str) -> str:
    stem = Path(name).stem.strip()
    return re.sub(r"^\d+\s*", "", stem).strip()


def split_sections(text: str):
    matches = list(SECTION_PATTERN.finditer(text))
    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(
            {
                "order": match.group(1),
                "question_type": match.group(2),
                "declared_count": int(match.group(3)),
                "title": match.group(0),
                "content": text[start:end].strip(),
            }
        )
    return sections


def parse_question_block(block: str, fallback_type: str, source_pdf: str, chapter: str, section: dict):
    block = block.strip()
    if not block:
        return None

    header_match = QUESTION_START_INLINE_PATTERN.match(block)
    if not header_match:
        return None

    question_no = int(header_match.group(1))
    question_type = header_match.group(2) or fallback_type
    body = block[header_match.end() :].strip()

    answer_match = ANSWER_PATTERN.search(body)
    answer = ""
    answer_text = ""
    if answer_match:
        answer = answer_match.group(1).strip()
        answer_text = answer_match.group(2).strip()
        body_without_answer = body[: answer_match.start()].strip()
    else:
        body_without_answer = body

    option_matches = list(OPTION_PATTERN.finditer(body_without_answer))
    options = []
    prompt = body_without_answer
    if option_matches:
        prompt = body_without_answer[: option_matches[0].start()].strip()
        for idx, match in enumerate(option_matches):
            start = match.end()
            end = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(body_without_answer)
            option_text = (match.group(2) + " " + body_without_answer[start:end]).strip()
            option_text = re.sub(r"\s+", " ", option_text)
            options.append({"label": match.group(1), "text": option_text})

    prompt = re.sub(r"\s+", " ", prompt).strip()
    answer_text = re.sub(r"\s+", " ", answer_text).strip()

    return ParsedQuestion(
        source_pdf=source_pdf,
        chapter=chapter,
        section_title=section["title"],
        section_order=section["order"],
        section_declared_count=section["declared_count"],
        question_no=question_no,
        question_type=question_type,
        prompt=prompt,
        options=options,
        answer=answer,
        answer_text=answer_text,
        raw_block=block,
    )


def parse_section_questions(section_content: str, fallback_type: str, source_pdf: str, chapter: str, section: dict):
    matches = list(QUESTION_START_INLINE_PATTERN.finditer(section_content))
    questions = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_content)
        block = section_content[start:end].strip()
        parsed = parse_question_block(block, fallback_type, source_pdf, chapter, section)
        if parsed:
            questions.append(parsed)
    return questions


def build_question_bank():
    all_questions: List[ParsedQuestion] = []
    source_files = sorted(PDF_ROOT.glob("*.pdf"))
    for pdf_path in source_files:
        chapter = chapter_from_filename(pdf_path.name)
        text = normalize_text(extract_pdf_text(pdf_path))
        sections = split_sections(text)
        for section in sections:
            all_questions.extend(
                parse_section_questions(
                    section_content=section["content"],
                    fallback_type=section["question_type"],
                    source_pdf=pdf_path.name,
                    chapter=chapter,
                    section=section,
                )
            )

    payload = {
        "source_root": str(PDF_ROOT),
        "output_file": str(OUTPUT_PATH),
        "question_count": len(all_questions),
        "questions": [asdict(item) for item in all_questions],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build_question_bank()
    print(json.dumps({"question_count": result["question_count"], "output_file": result["output_file"]}, ensure_ascii=False))
