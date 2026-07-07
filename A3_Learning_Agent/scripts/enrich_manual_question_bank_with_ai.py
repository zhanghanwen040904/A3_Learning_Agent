import json
import shutil
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ai.json_utils import extract_json_object
from ai.spark_api import spark_chat


QUESTION_BANK_PATH = PROJECT_ROOT / "rag_data" / "manual_question_bank" / "manual_question_bank_system.json"
BACKUP_PATH = PROJECT_ROOT / "rag_data" / "manual_question_bank" / "manual_question_bank_system.backup_before_ai.json"


GENERIC_EXPLANATION_MARKERS = [
    "这道题考查的是",
    "这道题不是只写一个结论",
]


def load_questions() -> list[dict]:
    return json.loads(QUESTION_BANK_PATH.read_text(encoding="utf-8"))


def save_questions(questions: list[dict]) -> None:
    QUESTION_BANK_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")


def needs_enrichment(item: dict, force: bool) -> bool:
    if force:
        return True
    explanation = str(item.get("explanation") or "")
    feedback_correct = str(item.get("feedback_correct") or "")
    feedback_wrong = str(item.get("feedback_wrong") or "")
    if not feedback_correct or not feedback_wrong:
        return True
    return any(marker in explanation for marker in GENERIC_EXPLANATION_MARKERS)


def build_prompt(item: dict) -> str:
    options = item.get("options") or []
    option_text = "\n".join(f"{opt.get('label')}. {opt.get('text')}" for opt in options) if options else "无"
    question_type = str(item.get("question_type") or "")
    knowledge_path = str(item.get("knowledge_path") or "")
    prompt = str(item.get("prompt") or "")
    reference_answer = str(item.get("reference_answer") or "")

    if question_type in {"单选题", "多选题", "判断题"}:
        requirement = """
你现在要为一道软件工程学习评估题生成“展示给学生看的精确解析信息”。

要求：
1. 必须严格围绕这道题本身，不要写泛泛而谈的模板话。
2. 对客观题，解析必须解释“为什么正确答案对”，并尽量点出其他选项为什么容易误选。
3. 易错点必须具体，最好指出学生最容易混淆的概念或阶段。
4. 得分点是学生答对这道题时应掌握的关键判断依据，2~4条即可。
5. feedback_correct 用一句自然的话说明答对的原因；feedback_wrong 用一句自然的话指出答错后该补的点。
6. 输出必须是 JSON，不要加 Markdown 代码块。

JSON 字段：
{
  "explanation": "字符串",
  "common_mistake": "字符串",
  "scoring_points": ["字符串", "..."],
  "feedback_correct": "字符串",
  "feedback_wrong": "字符串"
}
"""
    else:
        requirement = """
你现在要为一道软件工程学习评估题生成“展示给学生看的精确解析信息”。

要求：
1. 必须严格围绕这道题本身，不要写模板化空话。
2. 解析要围绕题目要点、参考答案和作答思路展开，适合学生看完就知道该怎么答。
3. 易错点要具体，指出学生容易漏掉哪一层、哪几个点。
4. 得分点要提炼成 2~4 条，是真正可以指导作答的要点。
5. feedback_correct 和 feedback_wrong 都要自然、简短、面向学生。
6. 输出必须是 JSON，不要加 Markdown 代码块。

JSON 字段：
{
  "explanation": "字符串",
  "common_mistake": "字符串",
  "scoring_points": ["字符串", "..."],
  "feedback_correct": "字符串",
  "feedback_wrong": "字符串"
}
"""

    return f"""{requirement}

题目信息：
- 题型：{question_type}
- 知识路径：{knowledge_path}
- 题干：{prompt}
- 选项：
{option_text}
- 参考答案：{reference_answer}
"""


def enrich_one(item: dict) -> dict:
    raw = spark_chat(build_prompt(item))
    data = extract_json_object(raw)
    if not data:
        raise RuntimeError(f"模型未返回可解析 JSON：{raw[:500]}")

    scoring_points = data.get("scoring_points") or []
    if not isinstance(scoring_points, list):
        scoring_points = [str(scoring_points)]

    item["explanation"] = str(data.get("explanation") or item.get("explanation") or "").strip()
    item["common_mistake"] = str(data.get("common_mistake") or item.get("common_mistake") or "").strip()
    item["scoring_points"] = [str(point).strip() for point in scoring_points if str(point).strip()][:4]
    item["feedback_correct"] = str(data.get("feedback_correct") or "").strip()
    item["feedback_wrong"] = str(data.get("feedback_wrong") or "").strip()
    item["enriched_by_ai"] = True
    item["enriched_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return item


def main(force: bool = False, limit: int | None = None) -> None:
    if not BACKUP_PATH.exists():
        shutil.copy2(QUESTION_BANK_PATH, BACKUP_PATH)

    questions = load_questions()
    target_indexes = [i for i, item in enumerate(questions) if needs_enrichment(item, force)]
    if limit:
        target_indexes = target_indexes[:limit]

    total = len(target_indexes)
    success_count = 0
    fail_count = 0

    for seq, idx in enumerate(target_indexes, start=1):
        item = questions[idx]
        try:
            enrich_one(item)
            success_count += 1
        except Exception as exc:
            fail_count += 1
            item["enrich_error"] = str(exc)
        if seq % 5 == 0 or seq == total:
            save_questions(questions)
            print(json.dumps({"progress": f"{seq}/{total}", "success": success_count, "fail": fail_count}, ensure_ascii=False))

    save_questions(questions)
    print(json.dumps({"done": True, "success": success_count, "fail": fail_count, "total": total}, ensure_ascii=False))


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    limit_value = None
    if "--limit" in sys.argv:
        try:
            limit_value = int(sys.argv[sys.argv.index("--limit") + 1])
        except Exception:
            limit_value = None
    main(force=force_flag, limit=limit_value)
