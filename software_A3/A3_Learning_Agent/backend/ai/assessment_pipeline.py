import json
import re
from pathlib import Path
from typing import Dict, List

from config import config
from .structured_course_data import load_semantic_chunks, normalize_title, split_sentences, summarize_text
from .rag import generated_kb_dir, questions_json_dir, knowledge_points_dir

ASSESSMENT_DIR = Path(config.RAG_SOURCE_DIR).parent / "assessment"
KNOWLEDGE_POINTS_PATH = ASSESSMENT_DIR / "knowledge_points.json"
QUESTION_BANK_PATH = ASSESSMENT_DIR / "question_bank.json"
MANUAL_QUESTION_BANK_PATH = Path(config.RAG_SOURCE_DIR).parent / "manual_question_bank" / "manual_question_bank_system.json"
GENERATED_QUESTION_BANK_DIR = generated_kb_dir() / "question_bank_json"

DEFAULT_COUNT = 5
DOMAIN_TERMS = [
    "软件工程",
    "软件生命周期",
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
    "状态图",
    "ER图",
    "DFD",
    "RUP",
]


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text or "")).strip("-").lower()
    return cleaned or "item"


def _extract_keywords(text: str, title: str = "", limit: int = 6) -> List[str]:
    source = "\n".join(filter(None, [normalize_title(title), str(text or "")]))
    results: List[str] = []
    title_keyword = normalize_title(title)
    if title_keyword:
        results.append(title_keyword)
    for term in DOMAIN_TERMS:
        if term in source and term not in results:
            results.append(term)
        if len(results) >= limit:
            return results[:limit]
    for part in re.split(r"[，、；;\n]", source):
        token = part.strip(" 。！？!?，,；;")
        if 2 <= len(token) <= 12 and token not in results:
            results.append(token)
        if len(results) >= limit:
            break
    return results[:limit]


def _make_reference_answer(content: str) -> str:
    return summarize_text(content, max_sentences=2)


def _make_explanation(knowledge_point: str, content: str) -> str:
    title = normalize_title(knowledge_point)
    sentences = split_sentences(content)
    if not sentences:
        return f"这道题主要考查你是否真正理解“{title}”的定义、核心特征和应用场景。"
    parts = [f"这道题的关键不是只背结论，而是说清“{title}”到底在讲什么。"]
    parts.append(f"其中最核心的一层意思是：{sentences[0]}。")
    if len(sentences) > 1:
        parts.append(f"进一步作答时，还可以补上：{sentences[1]}。")
    if len(sentences) > 2:
        parts.append(f"如果想拿到更高分，最好再结合“{sentences[2]}”来展开。")
    return "".join(parts)


def _make_common_mistake(knowledge_point: str, content: str) -> str:
    title = normalize_title(knowledge_point)
    text = str(content or "")
    keywords = _extract_keywords(text, title=knowledge_point, limit=4)
    if "区别" in text or "不同" in text or "对比" in text:
        return f"这类题最容易失分的地方，是只把“{title}”单独解释一遍，却没有和相近概念做出清晰区分。"
    if "步骤" in text or "流程" in text or "阶段" in text:
        return f"这类题常见的问题是只写出几个关键词，却没有按顺序说明“{title}”的关键步骤。"
    if "优点" in text or "缺点" in text:
        return f"回答“{title}”时，很多同学会只写优点或只写缺点，导致观点不完整。"
    if "应用" in text or "场景" in text:
        return f"关于“{title}”，常见失分点是只会背定义，却说不出它适合解决什么问题、能用在哪些场景。"
    if keywords:
        return f"这道题常见的问题是答案写得比较笼统，没有围绕“{'、'.join(keywords[:3])}”这些关键点展开。"
    return f"这道题常见失分点是只给出笼统表述，没有把“{title}”的定义、特点和实际意义说完整。"


def _make_scoring_points(knowledge_point: str, content: str) -> List[str]:
    title = normalize_title(knowledge_point)
    keywords = _extract_keywords(content, title=knowledge_point, limit=5)
    points = []
    if title:
        points.append(f"先准确说明“{title}”的基本定义。")
    for keyword in keywords:
        normalized = normalize_title(keyword)
        if normalized and normalized != title:
            points.append(f"回答中明确提到“{normalized}”这一关键内容。")
    text = str(content or "")
    if any(token in text for token in ["应用", "场景", "案例"]):
        points.append("能结合一个具体应用场景来说明它的作用。")
    elif any(token in text for token in ["步骤", "流程", "阶段"]):
        points.append("表述时体现出前后顺序或流程关系。")
    else:
        points.append("不要只列名词，要把各个要点之间的关系说清楚。")
    deduped = []
    for point in points:
        if point not in deduped:
            deduped.append(point)
    return deduped[:4]


def _make_prompt(knowledge_point: str, knowledge_type: str, tags: List[str]) -> str:
    title = normalize_title(knowledge_point)
    if knowledge_type == "comparison":
        return f"请说明“{title}”与相关概念的区别，并概括其核心要点。"
    if knowledge_type in {"method", "process_model", "phase"}:
        return f"请结合步骤或阶段，解释知识点“{title}”。"
    if tags:
        return f"请围绕“{title}”说明其核心内容，并适当提及 { '、'.join(tags[:2]) }。"
    return f"请解释知识点“{title}”。"


def _build_knowledge_points_from_question_bank(question_bank: List[dict]) -> List[dict]:
    knowledge_points: List[dict] = []
    node_index: Dict[str, str] = {}

    def ensure_node(path_parts: List[str], source: str, summary: str, keywords: List[str]) -> str:
        path_text = "/".join(path_parts)
        if path_text in node_index:
            return node_index[path_text]
        parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else None
        parent_id = node_index.get(parent_path) if parent_path else None
        node_id = f"kp-{_slug(path_text)}"
        node_index[path_text] = node_id
        knowledge_points.append(
            {
                "id": node_id,
                "name": path_parts[-1],
                "path": path_text,
                "parent_id": parent_id,
                "document": source,
                "summary": summary,
                "keywords": keywords,
                "children": [],
            }
        )
        if parent_id:
            for item in knowledge_points:
                if item["id"] == parent_id and node_id not in item["children"]:
                    item["children"].append(node_id)
                    break
        return node_id

    for item in question_bank:
        raw_path = str(item.get("knowledge_path") or "").strip()
        path_parts = [normalize_title(part) for part in raw_path.split("/") if normalize_title(part)]
        if not path_parts:
            fallback = normalize_title(item.get("knowledge_point") or "软件工程")
            path_parts = [fallback]

        summary = str(item.get("explanation") or item.get("reference_answer") or "").strip()
        keywords = item.get("keywords") or _extract_keywords(
            " ".join(
                [
                    str(item.get("prompt") or ""),
                    str(item.get("reference_answer") or ""),
                    str(item.get("knowledge_point") or ""),
                ]
            ),
            str(item.get("knowledge_point") or ""),
        )
        source = str(item.get("source_document") or "")

        for depth in range(1, len(path_parts) + 1):
            ensure_node(path_parts[:depth], source, summary, keywords)

    return knowledge_points


def _load_manual_question_bank() -> List[dict]:
    if not MANUAL_QUESTION_BANK_PATH.exists():
        return []
    try:
        payload = json.loads(MANUAL_QUESTION_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _build_from_semantic_chunks() -> tuple[List[dict], List[dict]]:
    semantic_chunks = load_semantic_chunks()
    knowledge_points: List[dict] = []
    question_bank: List[dict] = []
    node_index: Dict[str, str] = {}

    def ensure_node(path_parts: List[str], source: str, summary: str, keywords: List[str]) -> str:
        path_text = "/".join(path_parts)
        if path_text in node_index:
            return node_index[path_text]
        parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else None
        parent_id = node_index.get(parent_path) if parent_path else None
        node_id = f"kp-{_slug(path_text)}"
        node_index[path_text] = node_id
        knowledge_points.append(
            {
                "id": node_id,
                "name": path_parts[-1],
                "path": path_text,
                "parent_id": parent_id,
                "document": source,
                "summary": summary,
                "keywords": keywords,
                "children": [],
            }
        )
        if parent_id:
            for item in knowledge_points:
                if item["id"] == parent_id and node_id not in item["children"]:
                    item["children"].append(node_id)
                    break
        return node_id

    seen_questions = set()
    for index, chunk in enumerate(semantic_chunks, start=1):
        path_parts = chunk["section_path"] or [chunk["knowledge_point"]]
        for depth in range(1, len(path_parts) + 1):
            partial = path_parts[:depth]
            ensure_node(
                partial,
                chunk["source"],
                chunk["summary"],
                _extract_keywords(chunk["content"], partial[-1]),
            )

        knowledge_path = "/".join(path_parts)
        question_id = f"q-{index}-{_slug(chunk['knowledge_point'])}"
        prompt = _make_prompt(chunk["knowledge_point"], chunk["knowledge_type"], chunk["tags"])
        dedupe_key = (knowledge_path, prompt)
        if dedupe_key in seen_questions:
            continue
        seen_questions.add(dedupe_key)
        question_bank.append(
            {
                "id": question_id,
                "knowledge_point": chunk["knowledge_point"],
                "knowledge_path": knowledge_path,
                "source_document": chunk["source"],
                "question_type": "short_answer",
                "difficulty": "basic" if len(chunk["content"]) < 260 else "improve",
                "prompt": prompt,
                "reference_answer": _make_reference_answer(chunk["content"]),
                "explanation": _make_explanation(chunk["knowledge_point"], chunk["content"]),
                "common_mistake": _make_common_mistake(chunk["knowledge_point"], chunk["content"]),
                "scoring_points": _make_scoring_points(chunk["knowledge_point"], chunk["content"]),
                "keywords": _extract_keywords(chunk["content"], chunk["knowledge_point"]),
                "pages": chunk["pages"],
                "tags": chunk["tags"],
                "knowledge_type": chunk["knowledge_type"],
                "chunk_id": chunk["chunk_id"],
            }
        )

    return knowledge_points, question_bank


def build_assessment_assets(force: bool = False) -> dict:
    ASSESSMENT_DIR.mkdir(parents=True, exist_ok=True)
    if not force and KNOWLEDGE_POINTS_PATH.exists() and QUESTION_BANK_PATH.exists() and not MANUAL_QUESTION_BANK_PATH.exists():
        return {
            "knowledge_points_path": str(KNOWLEDGE_POINTS_PATH),
            "question_bank_path": str(QUESTION_BANK_PATH),
            "knowledge_point_count": len(load_knowledge_points()),
            "question_count": len(load_question_bank()),
            "status": "loaded",
            "bank_source": "manual" if MANUAL_QUESTION_BANK_PATH.exists() else "semantic_generated",
        }

    manual_question_bank = _load_manual_question_bank()
    if manual_question_bank:
        question_bank = manual_question_bank
        knowledge_points = _build_knowledge_points_from_question_bank(question_bank)
        source = "manual"
    else:
        knowledge_points, question_bank = _build_from_semantic_chunks()
        source = "semantic_generated"
    KNOWLEDGE_POINTS_PATH.write_text(json.dumps(knowledge_points, ensure_ascii=False, indent=2), encoding="utf-8")
    QUESTION_BANK_PATH.write_text(json.dumps(question_bank, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "knowledge_points_path": str(KNOWLEDGE_POINTS_PATH),
        "question_bank_path": str(QUESTION_BANK_PATH),
        "knowledge_point_count": len(knowledge_points),
        "question_count": len(question_bank),
        "status": "created",
        "bank_source": source,
    }


def load_knowledge_points() -> List[dict]:
    rag_knowledge_points = _load_rag_knowledge_points()
    if rag_knowledge_points:
        return rag_knowledge_points
    if not KNOWLEDGE_POINTS_PATH.exists():
        build_assessment_assets(force=True)
    return json.loads(KNOWLEDGE_POINTS_PATH.read_text(encoding="utf-8"))


def _load_rag_knowledge_points() -> List[dict]:
    items: List[dict] = []
    folder = knowledge_points_dir()
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload.get("knowledge_points") or payload.get("items") or payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = normalize_title(row.get("title") or row.get("name") or "")
            content = str(row.get("content") or row.get("description") or row.get("source_text") or "").strip()
            section_path = row.get("section_path") or []
            if not isinstance(section_path, list):
                section_path = [str(section_path)] if section_path else []
            if not title:
                continue
            items.append(
                {
                    "id": row.get("knowledge_id") or row.get("node_id") or row.get("chunk_id") or f"kp-{_slug(title)}",
                    "name": title,
                    "path": "/".join(section_path) if section_path else title,
                    "parent_id": row.get("parent_id"),
                    "document": row.get("source_file") or path.name,
                    "summary": str(row.get("content_preview") or content[:120]).strip(),
                    "keywords": row.get("keywords") or _extract_keywords(content, title),
                    "children": row.get("children") or [],
                }
            )
    return items


def _normalize_generated_question_item(item: dict) -> dict:
    related_titles = item.get("related_knowledge_titles") or item.get("knowledge_points") or []
    primary_titles = item.get("primary_knowledge_titles") or related_titles
    prerequisite_titles = item.get("prerequisite_knowledge_titles") or []
    pages = item.get("pages") or []
    section_path = item.get("section_path") or []
    stem = str(item.get("stem") or item.get("content") or item.get("prompt") or "").strip()
    return {
        "id": item.get("question_id") or item.get("id") or f"generated-{len(stem)}",
        "question_id": item.get("question_id") or item.get("id") or "",
        "knowledge_point": (primary_titles[0] if primary_titles else (related_titles[0] if related_titles else "")),
        "knowledge_path": "/".join(section_path) if isinstance(section_path, list) else str(section_path or ""),
        "chapter": section_path[1] if isinstance(section_path, list) and len(section_path) > 1 else "",
        "source_document": item.get("source_file") or "",
        "question_type": item.get("question_type") or "",
        "difficulty": item.get("difficulty_level") or item.get("difficulty") or "basic",
        "prompt": stem,
        "stem": stem,
        "options": item.get("options") or [],
        "reference_answer": item.get("answer") or "",
        "explanation": item.get("analysis") or "",
        "common_mistake": item.get("common_mistake") or "",
        "scoring_points": item.get("scoring_points") or [],
        "keywords": item.get("keywords") or [],
        "pages": pages,
        "tags": item.get("tags") or [],
        "knowledge_type": item.get("knowledge_type") or "",
        "chunk_id": item.get("chunk_id") or "",
        "related_knowledge_titles": related_titles,
        "primary_knowledge_titles": primary_titles,
        "prerequisite_knowledge_titles": prerequisite_titles,
        "related_knowledge": item.get("related_knowledge") or [],
        "confidence": item.get("confidence") or 0,
        "requires_image": bool(item.get("requires_image")),
        "generated_by_llm": bool(item.get("generated_by_llm")),
        "section_path": section_path if isinstance(section_path, list) else [],
    }


def _load_generated_question_bank() -> List[dict]:
    questions_dir = questions_json_dir()
    if questions_dir.exists():
        items: List[dict] = []
        for path in sorted(questions_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            rows = payload.get("questions") or payload.get("items") or payload if isinstance(payload, list) else []
            for item in rows:
                if isinstance(item, dict):
                    items.append(_normalize_generated_question_item(item))
        if items:
            return items

    if not GENERATED_QUESTION_BANK_DIR.exists():
        return []
    items: List[dict] = []
    for path in sorted(GENERATED_QUESTION_BANK_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("questions", []) if isinstance(payload, dict) else []:
            if isinstance(item, dict):
                items.append(_normalize_generated_question_item(item))
    return items


def load_question_bank() -> List[dict]:
    manual_question_bank = _load_manual_question_bank()
    if manual_question_bank:
        return manual_question_bank
    generated_question_bank = _load_generated_question_bank()
    if generated_question_bank:
        return generated_question_bank
    if not QUESTION_BANK_PATH.exists():
        build_assessment_assets(force=True)
    return json.loads(QUESTION_BANK_PATH.read_text(encoding="utf-8"))


def _normalize_match_text(text: str) -> str:
    text = normalize_title(str(text or ""))
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text.lower()


def _expand_focus_terms(focus_points: List[str]) -> List[str]:
    expanded = []
    for item in focus_points:
        raw = str(item or "").strip()
        if not raw:
            continue
        candidates = [raw]
        candidates.extend(re.split(r"[、，,；;>/-]+", raw))
        for candidate in candidates:
            normalized = normalize_title(candidate)
            cleaned = _normalize_match_text(candidate)
            for token in [normalized, cleaned]:
                if token and token not in expanded:
                    expanded.append(token)
    return expanded


def _score_question_match(item: dict, focus_terms: List[str], target: str, preferred_difficulties: List[str] | None = None) -> int:
    knowledge_point = str(item.get("knowledge_point") or "")
    knowledge_path = str(item.get("knowledge_path") or "")
    chapter = str(item.get("chapter") or "")
    keywords = [str(part or "") for part in (item.get("keywords") or [])]
    tags = [str(part or "") for part in (item.get("tags") or [])]
    related_titles = [str(part or "") for part in (item.get("related_knowledge_titles") or [])]
    primary_titles = [str(part or "") for part in (item.get("primary_knowledge_titles") or [])]
    prerequisite_titles = [str(part or "") for part in (item.get("prerequisite_knowledge_titles") or [])]

    normalized_fields = {
        "knowledge_point": _normalize_match_text(knowledge_point),
        "knowledge_path": _normalize_match_text(knowledge_path),
        "chapter": _normalize_match_text(chapter),
        "keywords": [_normalize_match_text(part) for part in keywords],
        "tags": [_normalize_match_text(part) for part in tags],
        "related_titles": [_normalize_match_text(part) for part in related_titles],
        "primary_titles": [_normalize_match_text(part) for part in primary_titles],
        "prerequisite_titles": [_normalize_match_text(part) for part in prerequisite_titles],
    }

    score = 0
    for focus in focus_terms:
        if not focus:
            continue
        if focus == normalized_fields["knowledge_point"]:
            score += 14
        elif focus in normalized_fields["knowledge_point"]:
            score += 10

        if focus == normalized_fields["chapter"]:
            score += 8
        elif focus in normalized_fields["chapter"]:
            score += 6

        if focus in normalized_fields["knowledge_path"]:
            score += 7

        if any(focus == keyword for keyword in normalized_fields["keywords"]):
            score += 5
        elif any(focus in keyword for keyword in normalized_fields["keywords"]):
            score += 3

        if any(focus == tag for tag in normalized_fields["tags"]):
            score += 4
        if any(focus == title for title in normalized_fields["primary_titles"]):
            score += 18
        elif any(focus in title for title in normalized_fields["primary_titles"]):
            score += 12
        if any(focus == title for title in normalized_fields["related_titles"]):
            score += 10
        elif any(focus in title for title in normalized_fields["related_titles"]):
            score += 6
        if any(focus == title for title in normalized_fields["prerequisite_titles"]):
            score += 5

    normalized_target = _normalize_match_text(target)
    if normalized_target:
        if any(normalized_target == title for title in normalized_fields["primary_titles"]):
            score += 24
        elif normalized_target == normalized_fields["knowledge_point"]:
            score += 20
        elif any(normalized_target in title for title in normalized_fields["primary_titles"]):
            score += 16
        elif normalized_target in normalized_fields["knowledge_path"]:
            score += 12
        elif normalized_target == normalized_fields["chapter"]:
            score += 10

    preferred_difficulties = preferred_difficulties or []
    if item.get("difficulty") in preferred_difficulties:
        score += 6
    elif item.get("difficulty") == "basic":
        score += 1
    elif item.get("difficulty") == "improve":
        score += 2

    return score


def _parse_profile_focus(profile: dict, mastery_records: List[dict]) -> List[str]:
    weak_points = str((profile or {}).get("weak_points") or "")
    profile_keywords = [item.strip() for item in re.split(r"[、，；;\s]+", weak_points) if item.strip()]
    mastery_keywords = [
        str(item.get("knowledge_point") or "").strip()
        for item in mastery_records
        if int(item.get("mastery_score") or 0) < 75 and str(item.get("knowledge_point") or "").strip()
    ]
    merged = []
    for item in profile_keywords + mastery_keywords:
        if item and item not in merged:
            merged.append(item)
    return merged


def _difficulty_preferences(stage_index: int | None) -> List[str]:
    if stage_index is None:
        return []
    if stage_index <= 0:
        return ["basic"]
    if stage_index == 1:
        return ["improve", "basic"]
    return ["application", "improve", "advanced"]


def generate_personalized_questions(profile: dict, mastery_records: List[dict], count: int = DEFAULT_COUNT, knowledge_point: str = "", knowledge_points: List[str] | None = None, stage_index: int | None = None, stage_title: str = "") -> dict:
    question_bank = load_question_bank()
    if not question_bank:
        build_assessment_assets()
        question_bank = load_question_bank()
    knowledge_points_tree = load_knowledge_points()
    focus_points = _parse_profile_focus(profile, mastery_records)

    stage_points = [str(item or "").strip() for item in (knowledge_points or []) if str(item or "").strip()]
    stage_title = str(stage_title or "").strip()
    target = str(knowledge_point or "").strip()
    if stage_title:
        focus_points = [stage_title] + focus_points
    if stage_points:
        focus_points = stage_points + focus_points
        target = stage_points[0]
    elif target:
        focus_points = [target] + focus_points
    focus_terms = _expand_focus_terms(focus_points)

    difficulty_preferences = _difficulty_preferences(stage_index)
    scored_questions = []
    for item in question_bank:
        score = _score_question_match(item, focus_terms, target, difficulty_preferences)
        scored_questions.append((score, item))

    scored_questions.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    if stage_index is not None:
        positive = [pair for pair in scored_questions if pair[0] > 0]
        rest = [pair for pair in scored_questions if pair[0] <= 0]
        if len(positive) > count:
            offset = (int(stage_index) * count) % len(positive)
            positive = positive[offset:] + positive[:offset]
            scored_questions = positive + rest
    selected: List[dict] = []
    used_paths = set()
    for score, item in scored_questions:
        path = item.get("knowledge_path")
        if len(selected) >= count:
            break
        if score <= 0 and focus_points:
            continue
        if path not in used_paths or score > 0:
            selected.append(item)
            used_paths.add(path)

    if len(selected) < count:
        for item in question_bank:
            if len(selected) >= count:
                break
            if item not in selected:
                selected.append(item)

    selected = [dict(item, order=index + 1) for index, item in enumerate(selected[:count])]
    recommended_paths = []
    for question in selected:
        path = question.get("knowledge_path")
        if path and path not in recommended_paths:
            recommended_paths.append(path)

    return {
        "focus_points": focus_points,
        "recommended_knowledge_points": recommended_paths,
        "knowledge_tree": knowledge_points_tree,
        "questions": selected,
        "question_count": len(selected),
    }


def assessment_status() -> dict:
    assets = build_assessment_assets()
    return {
        **assets,
        "knowledge_points_exists": KNOWLEDGE_POINTS_PATH.exists(),
        "question_bank_exists": QUESTION_BANK_PATH.exists(),
        "manual_question_bank_exists": MANUAL_QUESTION_BANK_PATH.exists(),
        "manual_question_bank_path": str(MANUAL_QUESTION_BANK_PATH),
    }
