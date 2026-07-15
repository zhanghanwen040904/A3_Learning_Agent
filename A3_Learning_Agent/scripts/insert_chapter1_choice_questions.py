import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = PROJECT_ROOT / "rag_data"
QUESTION_PATH = next((RAG_ROOT / "questions_json").glob("*.json"))
QUESTION_BANK_PATH = next((RAG_ROOT / "question_bank_json").glob("*.json"))
STUDENT_KB_PATH = next((RAG_ROOT / "student_knowledge_base_json").glob("*.json"))


def resolve_primary_knowledge_path() -> Path:
    candidates = [
        path
        for path in (RAG_ROOT / "knowledge_points_json").glob("*.json")
        if ".bak_" not in path.name
    ]
    ranked = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            points = payload.get("knowledge_points", []) if isinstance(payload, dict) else []
            ranked.append((len(points), os.path.getsize(path), path))
        except Exception:
            continue
    if not ranked:
        raise FileNotFoundError("no usable knowledge_points_json file found")
    ranked.sort(reverse=True)
    return ranked[0][2]


KNOWLEDGE_PATH = resolve_primary_knowledge_path()

SECTION_PATH = ["软件工程", "软件工程学概述", "第 1 章 软件工程概论", "选择题"]
SECTION_TITLE = "第 1 章 软件工程概论 选择题"
SOURCE_Q = r"C:\Users\ASUS\Desktop\新建文件夹\timu\1\choice_generated.txt"
SOURCE_A = r"C:\Users\ASUS\Desktop\新建文件夹\timu\1\choice_generated_answer.txt"


def stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:12]}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shutil.copy2(path, path.with_name(f"{path.name}.bak_{stamp}"))


def build_knowledge_lookup() -> dict:
    payload = load_json(KNOWLEDGE_PATH)
    return {item.get("knowledge_id"): item for item in payload.get("knowledge_points", [])}


def knowledge_ref(item: dict, score: int = 100) -> dict:
    learning_location = item.get("learning_location") or {}
    return {
        "knowledge_id": item.get("knowledge_id"),
        "node_id": item.get("knowledge_id"),
        "title": item.get("title"),
        "section_path": item.get("section_path") or [],
        "learning_location": learning_location,
        "pages": item.get("pages") or learning_location.get("pages") or [],
        "knowledge_type": item.get("knowledge_type") or "main_knowledge",
        "score": score,
        "confidence": 0.98,
        "match_reasons": ["manual_chapter1_choice_mapping"],
    }


CHOICE_QUESTIONS = [
    {
        "no": 13,
        "stem": "13. 下列哪一项最准确地反映了“软件危机”的典型表现？",
        "options": [
            "A. 硬件价格长期高于软件价格",
            "B. 软件开发和维护中经常出现进度失控、成本超支、质量难以保证等问题",
            "C. 程序只能使用低级语言编写",
            "D. 计算机系统无法存储大型程序",
        ],
        "answer": "B",
        "analysis": "软件危机主要表现为软件开发和维护难以控制，常见问题包括进度延期、成本超支、质量不可靠、维护困难等。",
        "knowledge_ids": ["chunk_3636eb0234ab", "merged_4bc95e3d0b75"],
        "keywords": ["软件危机", "成本超支", "进度失控", "质量问题", "维护困难"],
    },
    {
        "no": 14,
        "stem": "14. 产生软件危机的根本原因通常与下列哪一项最密切相关？",
        "options": [
            "A. 软件是逻辑产品，规模和复杂性不断提高，而开发方式长期缺乏工程化管理",
            "B. 所有软件都必须依赖同一种硬件平台运行",
            "C. 程序设计语言数量过少，不能表达复杂算法",
            "D. 用户在软件开发中完全不需要参与",
        ],
        "answer": "A",
        "analysis": "软件危机的成因既包括软件自身的复杂性、不可见性和易变性，也包括开发组织没有采用系统的工程方法和有效管理。",
        "knowledge_ids": ["merged_6d67ce0735d2", "chunk_3636eb0234ab"],
        "keywords": ["软件危机原因", "软件复杂性", "工程化管理", "软件不可见性"],
    },
    {
        "no": 15,
        "stem": "15. 下列哪一项属于消除软件危机的重要途径？",
        "options": [
            "A. 只增加程序员人数，不改变开发方法",
            "B. 在开发完成后再考虑需求和质量问题",
            "C. 采用软件工程方法，综合运用技术方法、工具和管理措施",
            "D. 尽量减少文档，使编码速度最快",
        ],
        "answer": "C",
        "analysis": "消除软件危机需要推广软件工程方法，把技术方法、工具和管理措施结合起来，规范软件开发与维护全过程。",
        "knowledge_ids": ["chunk_eb05843908ed", "merged_433b7b2acd16", "merged_1e0e0e7583ae"],
        "keywords": ["消除软件危机", "软件工程方法", "工具", "管理措施", "文档"],
    },
    {
        "no": 16,
        "stem": "16. 关于软件生命周期，下列说法正确的是哪一项？",
        "options": [
            "A. 软件生命周期只包括编码和测试两个阶段",
            "B. 软件交付后生命周期立即结束，不再需要维护",
            "C. 软件生命周期覆盖从问题定义、开发到运行维护的全过程",
            "D. 生命周期模型与项目管理没有关系",
        ],
        "answer": "C",
        "analysis": "软件生命周期描述软件从提出、定义、开发、使用到维护的全过程，分阶段管理能增强软件项目的可见性和可控性。",
        "knowledge_ids": ["merged_a163a9ca09dc", "merged_8e9b90ea0329"],
        "keywords": ["软件生命周期", "问题定义", "开发", "运行维护", "项目管理"],
    },
    {
        "no": 17,
        "stem": "17. 当需求比较明确、开发过程希望按阶段顺序推进，并以文档和评审控制进度时，最典型的软件过程模型是下列哪一项？",
        "options": [
            "A. 瀑布模型",
            "B. 喷泉模型",
            "C. 螺旋模型",
            "D. 极限编程",
        ],
        "answer": "A",
        "analysis": "瀑布模型按阶段顺序组织开发工作，强调阶段成果、文档和评审，适合需求较明确且变更较少的项目。",
        "knowledge_ids": ["merged_3478dbb9cdc3", "merged_8e9b90ea0329"],
        "keywords": ["瀑布模型", "软件过程", "阶段顺序", "文档", "评审"],
    },
]


def build_question(item: dict, knowledge_lookup: dict) -> dict:
    stem = item["stem"].strip()
    answer = item["answer"].strip()
    option_text = next((option for option in item["options"] if option.startswith(f"{answer}.")), "")
    reference_answer = f"{answer}：{option_text[3:].strip()}\n{item['analysis']}"
    refs = [
        knowledge_ref(knowledge_lookup[kid], max(88, 100 - index * 4))
        for index, kid in enumerate(item["knowledge_ids"])
        if kid in knowledge_lookup
    ]
    titles = [ref["title"] for ref in refs]
    qid = stable_id("question", f"chapter1_choice:{item['no']}:{stem}")
    aid = stable_id("answer", f"chapter1_choice:{item['no']}:{answer}:{item['analysis']}")
    link_id = stable_id("qa_link", f"{qid}:{aid}")
    learning_location = {
        "unit": "软件工程",
        "chapter": "软件工程学概述",
        "section": "第 1 章 软件工程概论",
        "subsection": "选择题",
        "path": SECTION_PATH,
        "path_text": " / ".join(SECTION_PATH),
        "pages": [],
    }
    return {
        "question_id": qid,
        "course": "软件工程",
        "source_file": SOURCE_Q,
        "section_title": SECTION_TITLE,
        "section_path": SECTION_PATH,
        "page": None,
        "pages": [],
        "question_type": "single_choice",
        "difficulty_level": "基础",
        "stem": stem,
        "options": item["options"],
        "content": stem + "\n" + "\n".join(item["options"]),
        "answer": answer,
        "reference_answer": reference_answer,
        "has_answer": True,
        "can_auto_grade": True,
        "analysis": item["analysis"],
        "images": [],
        "question_images": [],
        "has_images": False,
        "has_question_images": False,
        "answer_images": [],
        "has_answer_images": False,
        "image_count": 0,
        "answer_image_count": 0,
        "related_knowledge": refs,
        "related_knowledge_ids": [ref["knowledge_id"] for ref in refs],
        "related_knowledge_node_ids": [ref["node_id"] for ref in refs],
        "related_knowledge_titles": titles,
        "primary_knowledge_titles": titles[:1],
        "prerequisite_knowledge_titles": [],
        "confidence": 0.98,
        "requires_image": False,
        "metadata": {
            "source_question_file": SOURCE_Q,
            "source_answer_file": SOURCE_A,
            "cleaning_method": "manual_generated_choice_questions",
            "replacement_scope": "append_chapter1_choice_questions",
            "chapter": "第 1 章 软件工程概论",
            "chapter_no": 1,
            "question_no": item["no"],
            "question_chapter_key": "chapter_1",
            "answer_id": aid,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "question_chapter_key": "chapter_1",
        "question_no_raw": str(item["no"]),
        "parent_question_id": None,
        "parent_stem": "",
        "is_complete_question": True,
        "knowledge_points": titles,
        "related_knowledge_match_score": 100,
        "question_no": item["no"],
        "question_no_int": item["no"],
        "sub_question_no": "",
        "answer_link_ids": [link_id],
        "answer_ids": [aid],
        "has_answer_link": True,
        "answer_link_confidence": 1.0,
        "answer_link_method": "manual_generated_choice_answer",
        "answer_links": [
            {
                "answer_id": aid,
                "confidence": 1.0,
                "method": "manual_generated_choice_answer",
                "answer_no": item["no"],
                "question_chapter_key": "chapter_1",
            }
        ],
        "learning_location": learning_location,
        "content_preview": stem[:180],
        "knowledge_relations": [],
        "answer_pages": [],
        "_v21_full_reference_answer": reference_answer,
        "keywords": item["keywords"],
    }


def sort_key(question: dict) -> tuple[int, int, str]:
    chapter = 99
    key = str(question.get("question_chapter_key") or "")
    if key.startswith("chapter_"):
        try:
            chapter = int(key.split("_", 1)[1])
        except ValueError:
            chapter = 99
    elif "第 1 章" in str(question.get("section_title") or ""):
        chapter = 1
    return chapter, int(question.get("question_no_int") or question.get("question_no") or 0), str(question.get("question_id") or "")


def update_payload(path: Path, questions: list[dict]) -> None:
    payload = load_json(path)
    existing = [
        question
        for question in payload.get("questions", [])
        if not (
            question.get("metadata", {}).get("replacement_scope") == "append_chapter1_choice_questions"
            or str(question.get("question_id") or "") in {item["question_id"] for item in questions}
        )
    ]
    for question in existing:
        if "第 1 章" not in str(question.get("section_title") or ""):
            continue
        question["question_chapter_key"] = "chapter_1"
        metadata = dict(question.get("metadata") or {})
        metadata["chapter_no"] = 1
        metadata["question_chapter_key"] = "chapter_1"
        question["metadata"] = metadata
        for link in question.get("answer_links") or []:
            if isinstance(link, dict):
                link["question_chapter_key"] = "chapter_1"
    payload["questions"] = sorted(existing + questions, key=sort_key)
    stats = dict(payload.get("stats") or {})
    stats["question_count"] = len(payload["questions"])
    stats["answered_question_count"] = sum(1 for question in payload["questions"] if question.get("has_answer"))
    stats["auto_gradable_question_count"] = sum(1 for question in payload["questions"] if question.get("can_auto_grade"))
    stats["answer_linked_question_count"] = sum(1 for question in payload["questions"] if question.get("has_answer_link"))
    stats["chapter1_choice_question_count"] = len(questions)
    stats["chapter1_question_count"] = sum(
        1
        for question in payload["questions"]
        if question.get("question_chapter_key") == "chapter_1" or "第 1 章" in str(question.get("section_title") or "")
    )
    if path == STUDENT_KB_PATH:
        stats["questions"] = stats["answer_linked_question_count"]
    payload["stats"] = stats
    payload["question_replacement"] = {
        **dict(payload.get("question_replacement") or {}),
        "chapter1_choice_questions": {
            "count": len(questions),
            "question_nos": [item["question_no"] for item in questions],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "method": "manual_generated_choice_questions",
        },
    }
    backup(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    knowledge_lookup = build_knowledge_lookup()
    questions = [build_question(item, knowledge_lookup) for item in CHOICE_QUESTIONS]
    missing = [item for item in questions if not item["related_knowledge_ids"]]
    if missing:
        raise RuntimeError(f"questions without knowledge mapping: {[item['question_no'] for item in missing]}")
    for path in (QUESTION_PATH, QUESTION_BANK_PATH, STUDENT_KB_PATH):
        update_payload(path, questions)
    print(f"inserted {len(questions)} chapter 1 choice questions")


if __name__ == "__main__":
    main()
