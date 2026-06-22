import json
import re
import base64
import html

from flask import Blueprint, request

from ai.agents import SafetyAgent, TutorAgent
from ai.spark_api import content_audit, see_dance_generate
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

chat_bp = Blueprint("chat", __name__)
tutor_agent = TutorAgent()
safety_agent = SafetyAgent()
WELCOME_MESSAGE = {
    "role": "assistant",
    "content": "我是软件工程课程多模态答疑助手，会先检索课程知识库，再基于大模型生成回答，并进行防幻觉复核。",
}


def normalize_markdown(text: str) -> str:
    content = str(text or "").strip()
    fenced = re.fullmatch(r"```(?:markdown|md|text)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = re.sub(r"^\s*```(?:markdown|md|text)?\s*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"^\s*```\s*$", "", content, flags=re.MULTILINE)
    content = "\n".join(line[4:] if line.startswith("    ") and not line.startswith("        ") else line for line in content.splitlines())
    return content.strip()


def _wrap_svg_text(text: str, max_chars: int = 12, max_lines: int = 2) -> list[str]:
    text = re.sub(r"\s+", "", str(text or "").strip())
    if not text:
        return []
    lines = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1] + "..."
    return lines


def _extract_diagram_section(answer_text: str) -> str:
    content = str(answer_text or "")
    match = re.search(r"##\s*二[、.．]\s*图解说明([\s\S]*?)(?=\n##\s*三[、.．]|\Z)", content)
    return (match.group(1) if match else content).strip()


def _extract_diagram_items(answer_text: str, question: str) -> dict:
    section = _extract_diagram_section(answer_text)
    title_match = re.search(r"(?:图解主旨|中心主题|主题)[:：]\s*([^\n。；;]+)", section)
    title = title_match.group(1).strip() if title_match else str(question or "软件工程知识图").strip()

    node_texts: list[str] = []
    relation_texts: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip().lstrip("-*•0123456789.、 ")
        if not line:
            continue
        if "->" in line or "→" in line or "关联" in line:
            relation_texts.append(line)
        if any(key in line for key in ("核心节点", "图中节点", "节点", "左侧内容", "右侧内容", "关键输入", "关键输出")):
            for part in re.split(r"[：:，,、/；;（）()\"\s]+", line):
                part = part.strip()
                if 2 <= len(part) <= 12 and part not in {"核心节点", "图中节点", "节点", "左侧内容", "右侧内容"}:
                    node_texts.append(part)

    for bullet in re.findall(r"^\s*[-*•]\s*([^\n]+)", section, flags=re.MULTILINE):
        for part in re.split(r"[：:，,、/；;（）()\"\s]+", bullet):
            part = part.strip()
            if 2 <= len(part) <= 12 and not part.startswith(("至少", "每个", "说明", "中心", "底部")):
                node_texts.append(part)

    default_nodes = ["需求分析", "总体设计", "目标差异", "输入输出", "产物文档", "关注重点", "前后衔接", "质量保障", "常见误区", "应用场景"]
    seen = set()
    nodes = []
    for item in node_texts + default_nodes:
        clean = re.sub(r"[`#_*<>|{}[\]]", "", item).strip()
        if clean and clean not in seen:
            seen.add(clean)
            nodes.append(clean)
        if len(nodes) >= 10:
            break

    relations = []
    for item in relation_texts:
        clean = re.sub(r"[`#_*<>|{}[\]]", "", item).strip()
        if clean and clean not in relations:
            relations.append(clean.replace("->", "→"))
        if len(relations) >= 5:
            break
    if not relations:
        relations = ["需求分析 → 总体设计", "用户需求 → 需求规格", "需求规格 → 架构设计", "架构设计 → 模块划分", "设计方案 → 编码测试"]

    return {"title": title[:26], "nodes": nodes, "relations": relations}


def _build_diagram_image(answer_text: str, question: str) -> str:
    data = _extract_diagram_items(answer_text, question)
    title = html.escape(data["title"] or "软件工程知识图")
    nodes = data["nodes"]
    relations = data["relations"]
    width, height = 1180, 680
    node_positions = [
        (70, 185), (250, 145), (450, 185), (650, 145), (850, 185),
        (160, 395), (360, 435), (560, 395), (760, 435), (940, 395),
    ]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        '<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="#f8fbff"/><stop offset="100%" stop-color="#eaf4ff"/></linearGradient>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#2563eb" flood-opacity="0.14"/></filter>',
        '</defs>',
        '<rect width="1180" height="680" rx="28" fill="url(#bg)"/>',
        '<rect x="34" y="34" width="1112" height="612" rx="24" fill="#ffffff" stroke="#bfdbfe" stroke-width="2"/>',
        f'<text x="590" y="86" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="34" font-weight="800" fill="#1d4ed8">{title}</text>',
        '<text x="590" y="122" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" fill="#64748b">软件工程知识图解</text>',
        '<rect x="470" y="286" width="240" height="90" rx="22" fill="#2563eb" filter="url(#shadow)"/>',
        '<text x="590" y="322" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="23" font-weight="800" fill="#ffffff">核心关系</text>',
        '<text x="590" y="352" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="17" fill="#dbeafe">目标 · 产物 · 衔接</text>',
    ]

    for x, y in node_positions:
        svg_parts.append(f'<path d="M590 331 C {590} {y + 50}, {x + 70} {331}, {x + 70} {y + 42}" stroke="#93c5fd" stroke-width="3" fill="none"/>')

    colors = ["#eff6ff", "#dbeafe", "#f0f9ff", "#e0f2fe"]
    for index, node in enumerate(nodes[:10]):
        x, y = node_positions[index]
        fill = colors[index % len(colors)]
        svg_parts.append(f'<rect x="{x}" y="{y}" width="150" height="84" rx="18" fill="{fill}" stroke="#60a5fa" stroke-width="2" filter="url(#shadow)"/>')
        lines = _wrap_svg_text(node, 7, 2)
        start_y = y + 36 if len(lines) == 1 else y + 30
        for line_index, line in enumerate(lines):
            svg_parts.append(
                f'<text x="{x + 75}" y="{start_y + line_index * 24}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="20" font-weight="700" fill="#0f3a78">{html.escape(line)}</text>'
            )

    rel_y = 560
    svg_parts.append('<rect x="70" y="528" width="1040" height="82" rx="18" fill="#f8fbff" stroke="#bfdbfe"/>')
    svg_parts.append('<text x="94" y="560" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" font-weight="800" fill="#1d4ed8">关系链</text>')
    for index, relation in enumerate(relations[:3]):
        text = html.escape(relation[:34])
        svg_parts.append(f'<text x="{210 + index * 300}" y="{rel_y}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="17" fill="#0f172a">{text}</text>')
    svg_parts.append('</svg>')
    raw_svg = "".join(svg_parts)
    encoded = base64.b64encode(raw_svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _session_id_for_request(user_id: int, payload: dict | None = None):
    session = resolve_profile_session(user_id, payload or {}, create_if_missing=False)
    return session["id"] if session else None


def _conversation_where(user_id: int, session_id):
    if session_id is None:
        return "user_id=%s AND profile_session_id IS NULL", (user_id,)
    return "user_id=%s AND profile_session_id=%s", (user_id, session_id)


def _load_messages(user_id: int, session_id):
    where, params = _conversation_where(user_id, session_id)
    row = mysql_db.query_one(f"SELECT messages FROM tutor_conversation WHERE {where} LIMIT 1", params)
    if not row:
        return [WELCOME_MESSAGE.copy()]
    try:
        messages = json.loads(row.get("messages") or "[]")
        messages = _clean_messages(messages)
        return messages if messages else [WELCOME_MESSAGE.copy()]
    except Exception:
        return [WELCOME_MESSAGE.copy()]


def _clean_messages(messages: list[dict]) -> list[dict]:
    clean_messages = []
    for item in messages[-80:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "assistant")
        content = normalize_markdown(item.get("content") or "")
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        video = str(item.get("video") or "")
        diagram_image = str(item.get("diagram_image") or "")
        if role == "assistant" and not content:
            continue
        if clean_messages and clean_messages[-1].get("role") == role and clean_messages[-1].get("content") == content:
            continue
        clean_messages.append({"role": role, "content": content, "sources": sources, "video": video, "diagram_image": diagram_image})
    return clean_messages


def _save_messages(user_id: int, session_id, messages: list[dict]) -> None:
    clean_messages = _clean_messages(messages)
    messages_json = json.dumps(clean_messages or [WELCOME_MESSAGE.copy()], ensure_ascii=False)
    where, params = _conversation_where(user_id, session_id)
    existing = mysql_db.query_one(f"SELECT id FROM tutor_conversation WHERE {where} LIMIT 1", params)
    if existing:
        mysql_db.update("tutor_conversation", {"messages": messages_json}, "id=%s", (existing["id"],))
    else:
        mysql_db.insert(
            "tutor_conversation",
            {
                "user_id": user_id,
                "profile_session_id": session_id,
                "messages": messages_json,
            },
        )


@chat_bp.post("/answer")
@login_required
def answer():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        question = str(payload["question"])
        if not content_audit(question):
            return fail("问题未通过讯飞内容审核", 403)

        session_id = _session_id_for_request(request.user_id, payload)
        history = payload.get("messages")
        if not isinstance(history, list):
            history = _load_messages(request.user_id, session_id)
        history = _clean_messages(history)
        if not history or history[-1].get("role") != "user" or history[-1].get("content") != question:
            history.append({"role": "user", "content": question})

        result = tutor_agent.answer(question)
        answer_text = normalize_markdown(result["answer"])
        if not content_audit(answer_text):
            return fail("答疑内容未通过讯飞内容审核", 403)

        video_url = ""
        if payload.get("need_video", False):
            video_url = see_dance_generate(f"请基于以下答疑内容生成60秒以内教学短视频：{answer_text[:1200]}")

        diagram_image = _build_diagram_image(answer_text, question)
        safety = safety_agent.review(answer_text, result.get("sources", []))
        assistant_message = {
            "role": "assistant",
            "content": answer_text,
            "sources": result.get("sources", []),
            "video": video_url,
            "diagram_image": diagram_image,
        }
        history.append(assistant_message)
        _save_messages(request.user_id, session_id, history)
        return success(
            {
                "answer": answer_text,
                "diagram": answer_text,
                "diagram_image": diagram_image,
                "video_url": video_url,
                "evidence": result.get("evidence", ""),
                "sources": result.get("sources", []),
                "safety": safety,
                "messages": history,
                "profile_session_id": session_id,
            },
            "答疑成功",
        )
    except Exception as exc:
        return fail("智能答疑失败", 500, {"error": str(exc)})


@chat_bp.post("/ask")
@login_required
def ask_alias():
    return answer()


@chat_bp.get("/history")
@login_required
def history():
    try:
        session_id = _session_id_for_request(request.user_id, {})
        return success(
            {"messages": _load_messages(request.user_id, session_id), "profile_session_id": session_id},
            "答疑历史读取成功",
        )
    except Exception as exc:
        return fail("答疑历史读取失败", 500, {"error": str(exc)})


@chat_bp.post("/history")
@login_required
def save_history():
    try:
        payload = request.get_json(silent=True) or {}
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return fail("messages必须是数组", 400)
        session_id = _session_id_for_request(request.user_id, payload)
        _save_messages(request.user_id, session_id, messages)
        return success({"profile_session_id": session_id}, "答疑历史保存成功")
    except Exception as exc:
        return fail("答疑历史保存失败", 500, {"error": str(exc)})


@chat_bp.delete("/history")
@login_required
def clear_history():
    try:
        session_id = _session_id_for_request(request.user_id, {})
        where, params = _conversation_where(request.user_id, session_id)
        mysql_db.execute(f"DELETE FROM tutor_conversation WHERE {where}", params)
        return success({"messages": [WELCOME_MESSAGE.copy()], "profile_session_id": session_id}, "答疑历史已清空")
    except Exception as exc:
        return fail("答疑历史清空失败", 500, {"error": str(exc)})
