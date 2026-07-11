from pathlib import Path

p = Path(r"e:\知识问答\A3_Learning_Agent\backend\api\knowledge_api.py")
s = p.read_text(encoding="utf-8")
old = """    result = []
    used_ids = set()
    for raw in extracted:"""
new = """    if chapter_items:
        formatted_items = []
        seen_question_ids = set()
        for item in sorted(
            chapter_items,
            key=lambda value: (_question_no_int(value.get("question_no")) or 10**9, str(value.get("sub_question_no") or "")),
        ):
            formatted = _format_bank_question(item)
            if formatted["question_id"] in seen_question_ids:
                continue
            seen_question_ids.add(formatted["question_id"])
            formatted["answer_status"] = "已匹配练习册答案" if formatted["has_answer"] else "暂无练习册匹配答案"
            formatted["source"] = formatted.get("source") or "MY 练习册题库"
            formatted_items.append(formatted)
        return formatted_items

    result = []
    used_ids = set()
    for raw in extracted:"""
if old not in s:
    raise SystemExit("target snippet not found")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("patched")
