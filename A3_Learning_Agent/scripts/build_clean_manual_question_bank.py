import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUAL_ROOT = PROJECT_ROOT / "rag_data" / "manual_question_bank"
DRAFT_PATH = MANUAL_ROOT / "manual_question_bank_draft.json"
CLEAN_OUTPUT_PATH = MANUAL_ROOT / "manual_question_bank_clean.json"
SYSTEM_OUTPUT_PATH = MANUAL_ROOT / "manual_question_bank_system.json"
REVIEW_OUTPUT_PATH = MANUAL_ROOT / "manual_question_bank_review_needed.json"


TYPE_MAP = {
    "单选题": "single_choice",
    "多选题": "multiple_choice",
    "判断题": "true_false",
    "填空题": "fill_blank",
    "简答题": "short_answer",
    "问答题": "short_answer",
    "分析题": "analysis",
    "综合题": "analysis",
}

DOMAIN_TERMS = [
    "软件工程",
    "软件危机",
    "软件生命周期",
    "生命周期模型",
    "可行性研究",
    "需求分析",
    "总体设计",
    "详细设计",
    "编码",
    "测试",
    "维护",
    "模块",
    "接口",
    "数据流图",
    "判定表",
    "判定树",
    "原型模型",
    "瀑布模型",
    "螺旋模型",
    "V模型",
    "耦合",
    "内聚",
]


def normalize_text(text: str) -> str:
    text = str(text or "").replace("\r", "")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text))


def slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text or "")).strip("-").lower()
    return cleaned or "item"


def clean_prompt(text: str) -> str:
    text = one_line(text)
    text = re.sub(r"^[（(]\s*[）)]\s*", "", text)
    text = re.sub(r"^\d+\s*[\.、]\s*", "", text)
    return text.strip(" ;；")


def extract_subjective_answer(raw_block: str) -> str:
    raw_block = normalize_text(raw_block)
    patterns = [
        r"正确答案[：:]\s*(.+)$",
        r"参考答案[：:]\s*(.+)$",
        r"答案[：:]\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_block, re.S)
        if match:
            return one_line(match.group(1))
    return ""


def normalize_choice_answer(answer: str) -> str:
    answer = str(answer or "").upper()
    letters = re.findall(r"[A-H]", answer)
    deduped = []
    for letter in letters:
        if letter not in deduped:
            deduped.append(letter)
    return "".join(deduped)


def build_reference_answer(item: dict) -> tuple[str, str]:
    options = item.get("options") or []
    answer = normalize_choice_answer(item.get("answer") or "")
    answer_text = one_line(item.get("answer_text") or "")

    if options and answer:
        option_map = {opt["label"].upper(): one_line(opt["text"]) for opt in options if opt.get("label")}
        chosen = [option_map[label] for label in answer if label in option_map]
        option_text = "；".join(chosen)
        if len(answer) == 1:
            reference = f"{answer}：{option_text}" if option_text else answer
        else:
            reference = f"{answer}：{option_text}" if option_text else answer
        return answer, reference

    subjective = answer_text or extract_subjective_answer(item.get("raw_block") or "")
    subjective = one_line(subjective)
    return "", subjective


def infer_knowledge_point(item: dict, prompt: str) -> str:
    quoted = re.search(r"[“\"]([^”\"]{2,30})[”\"]", prompt)
    if quoted:
        return one_line(quoted.group(1))

    chapter = one_line(item.get("chapter") or "")
    if chapter:
        return chapter
    return "软件工程"


def infer_difficulty(question_type: str, prompt: str, reference_answer: str) -> str:
    text_size = len(prompt) + len(reference_answer)
    if question_type in {"analysis", "short_answer"}:
        if text_size >= 180:
            return "hard"
        if text_size >= 80:
            return "improve"
        return "basic"
    if question_type == "multiple_choice":
        return "improve"
    return "basic"


def extract_keywords(prompt: str, reference_answer: str, chapter: str, limit: int = 6) -> list[str]:
    source = " ".join([prompt, reference_answer, chapter])
    result = []

    for term in DOMAIN_TERMS:
        if term in source and term not in result:
            result.append(term)
        if len(result) >= limit:
            return result[:limit]

    for token in re.findall(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9]{1,15}", source):
        token = token.strip()
        if token.isdigit():
            continue
        if len(token) < 2:
            continue
        if token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result[:limit]


def build_scoring_points(question_type: str, knowledge_point: str, prompt: str, reference_answer: str, answer_code: str) -> list[str]:
    points = []
    if question_type in {"single_choice", "multiple_choice", "true_false"}:
        points.append(f"先判断题目考查的是“{knowledge_point}”中的哪个核心概念。")
        if answer_code:
            points.append(f"明确选出正确答案：{answer_code}。")
        if "：" in reference_answer:
            detail = reference_answer.split("：", 1)[1].strip()
            if detail:
                points.append(f"知道正确选项对应的关键内容：{detail}。")
        points.append("不要只凭字面相似作答，要抓住定义、特征或适用场景。")
        return points[:4]

    chunks = re.split(r"[；;。]\s*|\s+\d+[）)]", reference_answer)
    chunks = [one_line(chunk) for chunk in chunks if one_line(chunk)]
    points.append(f"先准确说明“{knowledge_point}”的核心定义或中心结论。")
    for chunk in chunks[:3]:
        if chunk != knowledge_point and chunk not in points:
            points.append(f"补充要点：{chunk}。")
    if len(points) < 4:
        points.append("作答时尽量按步骤、层次或因果关系展开。")
    return points[:4]


def build_explanation(question_type: str, knowledge_point: str, reference_answer: str, prompt: str) -> str:
    if question_type in {"single_choice", "multiple_choice", "true_false"}:
        if "：" in reference_answer:
            answer_code, detail = reference_answer.split("：", 1)
            return f"这道题考查的是“{knowledge_point}”的基本判断。正确答案是 {answer_code.strip()}，关键依据是：{detail.strip()}。"
        return f"这道题考查的是“{knowledge_point}”的基本判断，作答时要抓住概念定义和特征。"

    answer_core = one_line(reference_answer)
    if len(answer_core) > 120:
        answer_core = answer_core[:120].rstrip("，；;。") + "……"
    return f"这道题不是只写一个结论，而是要围绕“{knowledge_point}”展开说明。作答时建议先说清核心定义，再补充关键步骤、特点或适用场景。可参考的核心内容是：{answer_core}"


def build_common_mistake(question_type: str, knowledge_point: str, reference_answer: str) -> str:
    if question_type in {"single_choice", "multiple_choice", "true_false"}:
        return f"这类题常见问题是只看字面词汇，不去区分“{knowledge_point}”相关概念之间的真实差异。"
    if any(word in reference_answer for word in ["步骤", "过程", "阶段", "先", "再"]):
        return f"这类题容易失分在于只罗列名词，没有按“{knowledge_point}”的步骤或层次组织答案。"
    return f"这类题容易失分在于只写结论，没有把“{knowledge_point}”的定义、特点和关键要点解释完整。"


def build_clean_record(index: int, item: dict) -> dict:
    prompt = clean_prompt(item.get("prompt") or "")
    answer_code, reference_answer = build_reference_answer(item)
    question_type_cn = one_line(item.get("question_type") or "")
    question_type = TYPE_MAP.get(question_type_cn, "short_answer")
    chapter = one_line(item.get("chapter") or "")
    knowledge_point = infer_knowledge_point(item, prompt)
    knowledge_path = f"软件工程/{chapter}/{knowledge_point}" if chapter and knowledge_point != chapter else f"软件工程/{knowledge_point}"
    keywords = extract_keywords(prompt, reference_answer, chapter)
    difficulty = infer_difficulty(question_type, prompt, reference_answer)
    explanation = build_explanation(question_type, knowledge_point, reference_answer, prompt)
    common_mistake = build_common_mistake(question_type, knowledge_point, reference_answer)
    scoring_points = build_scoring_points(question_type, knowledge_point, prompt, reference_answer, answer_code)

    clean_item = {
        "id": f"manual-q-{index:03d}-{slug(knowledge_point)}",
        "source_pdf": item.get("source_pdf"),
        "chapter": chapter,
        "section_title": one_line(item.get("section_title") or ""),
        "question_no": item.get("question_no"),
        "question_type_cn": question_type_cn,
        "question_type": question_type,
        "knowledge_point": knowledge_point,
        "knowledge_path": knowledge_path,
        "difficulty": difficulty,
        "prompt": prompt,
        "options": item.get("options") or [],
        "answer": answer_code,
        "reference_answer": reference_answer,
        "explanation": explanation,
        "common_mistake": common_mistake,
        "scoring_points": scoring_points,
        "keywords": keywords,
        "tags": [chapter, question_type_cn],
        "source_document": item.get("source_pdf"),
        "pages": [],
        "knowledge_type": "",
        "chunk_id": "",
        "raw_block": item.get("raw_block") or "",
    }
    return clean_item


def collect_review_reasons(item: dict) -> list[str]:
    reasons = []
    if not str(item.get("prompt") or "").strip():
        reasons.append("empty_prompt")

    question_type = item.get("question_type")
    if question_type in {"single_choice", "multiple_choice", "true_false"}:
        if not item.get("options"):
            reasons.append("missing_options")
        if not str(item.get("answer") or "").strip():
            reasons.append("missing_answer_code")
        if not str(item.get("reference_answer") or "").strip():
            reasons.append("missing_reference_answer")
    else:
        if not str(item.get("reference_answer") or "").strip():
            reasons.append("missing_reference_answer")
    return reasons


def build_outputs() -> dict:
    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    clean_questions = []
    system_questions = []
    review_needed = []

    for index, item in enumerate(draft.get("questions") or [], start=1):
        clean_item = build_clean_record(index, item)
        clean_questions.append(clean_item)
        review_reasons = collect_review_reasons(clean_item)
        if review_reasons:
            review_needed.append(
                {
                    **clean_item,
                    "review_reasons": review_reasons,
                }
            )
            continue

        system_questions.append(
            {
                "id": clean_item["id"],
                "knowledge_point": clean_item["knowledge_point"],
                "knowledge_path": clean_item["knowledge_path"],
                "source_document": clean_item["source_document"],
                "question_type": clean_item["question_type_cn"],
                "difficulty": clean_item["difficulty"],
                "prompt": clean_item["prompt"],
                "reference_answer": clean_item["reference_answer"],
                "explanation": clean_item["explanation"],
                "common_mistake": clean_item["common_mistake"],
                "scoring_points": clean_item["scoring_points"],
                "keywords": clean_item["keywords"],
                "pages": clean_item["pages"],
                "tags": clean_item["tags"],
                "knowledge_type": clean_item["knowledge_type"],
                "chunk_id": clean_item["chunk_id"],
                "options": clean_item["options"],
                "answer": clean_item["answer"],
                "chapter": clean_item["chapter"],
                "section_title": clean_item["section_title"],
                "question_no": clean_item["question_no"],
            }
        )

    clean_payload = {
        "source_file": str(DRAFT_PATH),
        "question_count": len(clean_questions),
        "questions": clean_questions,
    }
    system_payload = {
        "source_file": str(DRAFT_PATH),
        "question_count": len(system_questions),
        "questions": system_questions,
    }
    review_payload = {
        "source_file": str(DRAFT_PATH),
        "question_count": len(review_needed),
        "questions": review_needed,
    }

    CLEAN_OUTPUT_PATH.write_text(json.dumps(clean_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SYSTEM_OUTPUT_PATH.write_text(json.dumps(system_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    REVIEW_OUTPUT_PATH.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "clean_output": str(CLEAN_OUTPUT_PATH),
        "system_output": str(SYSTEM_OUTPUT_PATH),
        "review_output": str(REVIEW_OUTPUT_PATH),
        "raw_question_count": len(clean_questions),
        "question_count": len(clean_questions),
        "usable_question_count": len(system_questions),
        "review_question_count": len(review_needed),
    }


if __name__ == "__main__":
    result = build_outputs()
    print(json.dumps(result, ensure_ascii=False))
