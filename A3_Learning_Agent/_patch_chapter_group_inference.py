from pathlib import Path

p = Path(r"e:\知识问答\A3_Learning_Agent\backend\api\knowledge_api.py")
s = p.read_text(encoding="utf-8")
old = """    bank_by_no: dict[int, list[dict]] = {}
    chapter_items: list[dict] = []
    chapter_key_prefix = f"第{chapter_no}章" if chapter_no else ""
    chapter_key_alt = f"chapter_{chapter_no}" if chapter_no else ""
    for item in question_bank:
        links = item.get("answer_links") or []
        key_text = " ".join(str(link.get("question_chapter_key") or "") for link in links)
        if chapter_key_prefix and chapter_key_prefix not in key_text and chapter_key_alt not in key_text:
            continue
        chapter_items.append(item)
        no = _question_no_int(item.get("question_no"))
        if no is not None:
            bank_by_no.setdefault(no, []).append(item)
"""
new = """    bank_by_no: dict[int, list[dict]] = {}
    chapter_items: list[dict] = []
    chapter_key_prefix = f"第{chapter_no}章" if chapter_no else ""
    chapter_key_alt = f"chapter_{chapter_no}" if chapter_no else ""
    chapter_group_first_page: dict[str, int] = {}
    for item in question_bank:
        links = item.get("answer_links") or []
        key = str((links[0] if links else {}).get("question_chapter_key") or "")
        pages = [page for page in item.get("pages") or [] if isinstance(page, int)]
        if key and pages:
            chapter_group_first_page[key] = min(chapter_group_first_page.get(key, pages[0]), pages[0])
    chapter_group_order = {
        key: index + 1
        for index, key in enumerate(sorted(chapter_group_first_page, key=lambda value: chapter_group_first_page[value]))
    }

    for item in question_bank:
        links = item.get("answer_links") or []
        key_text = " ".join(str(link.get("question_chapter_key") or "") for link in links)
        first_key = str((links[0] if links else {}).get("question_chapter_key") or "")
        explicit_hit = bool(chapter_key_prefix and (chapter_key_prefix in key_text or chapter_key_alt in key_text))
        inferred_hit = bool(chapter_no and first_key and chapter_group_order.get(first_key) == chapter_no)
        if chapter_no and not explicit_hit and not inferred_hit:
            continue
        chapter_items.append(item)
        no = _question_no_int(item.get("question_no"))
        if no is not None:
            bank_by_no.setdefault(no, []).append(item)
"""
if old not in s:
    raise SystemExit("chapter filter snippet not found")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("patched chapter group inference")
