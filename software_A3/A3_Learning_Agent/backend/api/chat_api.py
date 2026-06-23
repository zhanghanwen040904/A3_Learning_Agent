import base64
import html
import json
import re

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
    "content": "我是软件工程课程多模态答疑助手，会先检索课程知识库，再基于大模型生成回答，并进行安全复核。",
}


def normalize_markdown(text: str) -> str:
    content = str(text or "").strip()
    fenced = re.fullmatch(r"```(?:markdown|md|text)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = re.sub(r"^\s*```(?:markdown|md|text)?\s*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"^\s*```\s*$", "", content, flags=re.MULTILINE)
    content = "\n".join(
        line[4:] if line.startswith("    ") and not line.startswith("        ") else line
        for line in content.splitlines()
    )
    return content.strip()


def _looks_mojibake(text: str) -> bool:
    sample = str(text or "")
    if not sample:
        return False
    bad_tokens = sample.count("�") + sample.count("锟") + sample.count("鎴") + sample.count("鐭") + sample.count("璇")
    return bad_tokens >= 3


def _clean_text(text: str, fallback: str = "") -> str:
    content = normalize_markdown(text)
    return fallback if _looks_mojibake(content) else content


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
        content = _clean_text(item.get("content") or "")
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        video = str(item.get("video") or "")
        diagram_image = str(item.get("diagram_image") or "")
        if not content and role == "assistant":
            continue
        if clean_messages and clean_messages[-1].get("role") == role and clean_messages[-1].get("content") == content:
            continue
        clean_messages.append(
            {
                "role": role,
                "content": content,
                "sources": sources,
                "video": video,
                "diagram_image": diagram_image,
            }
        )
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


def _section_body(answer_text: str, title_number: str, next_numbers: str = "三四") -> str:
    content = normalize_markdown(answer_text)
    pattern = rf"(?:^|\n)##\s*{title_number}[、.．]\s*[^。\n]*\n?([\s\S]*?)(?=\n##\s*[{next_numbers}][、.．]|\Z)"
    match = re.search(pattern, content)
    return (match.group(1) if match else content).strip()


def _shorten(text: str, max_len: int = 18) -> str:
    content = re.sub(r"[*_`#>\-|]+", "", str(text or ""))
    content = re.sub(r"\s+", "", content)
    return content[:max_len] if content else ""


def _extract_terms(text: str, limit: int = 8) -> list[str]:
    stop_words = {
        "核心观点",
        "图解主旨",
        "画面布局",
        "图中节点",
        "关系节点",
        "视觉标注",
        "中心主题",
        "左侧内容",
        "右侧内容",
        "底部总结",
        "箭头方向",
    }
    terms: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().lstrip("-*•0123456789.、 ")
        if not line:
            continue
        head = re.split(r"[：:，,。；;（）()\"“”/]+", line)[0]
        term = _shorten(head, 14)
        if 2 <= len(term) <= 14 and term not in stop_words:
            terms.append(term)
    seen = set()
    result = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            result.append(term)
        if len(result) >= limit:
            break
    return result


def _diagram_model(answer_text: str, question: str) -> dict:
    combined = f"{question}\n{answer_text}"
    if "需求分析" in combined and "总体设计" in combined:
        return {
            "title": "需求分析与总体设计的顺序关系",
            "subtitle": "先明确做什么，再决定怎么组织系统",
            "flow": [
                ("需求分析", "理解用户需要"),
                ("需求规格说明书", "形成设计输入"),
                ("总体设计", "确定系统结构"),
                ("模块划分", "分解系统职责"),
                ("接口定义", "约定协作边界"),
                ("详细设计", "细化内部逻辑"),
            ],
            "left": {
                "title": "需求分析",
                "color": "#2563eb",
                "items": ["关注做什么", "输入用户需求", "输出SRS文档", "识别功能边界"],
            },
            "right": {
                "title": "总体设计",
                "color": "#0ea5e9",
                "items": ["关注怎么组织", "输入SRS文档", "输出架构方案", "划分模块接口"],
            },
            "relations": ["需求分析是前置阶段", "SRS是总体设计输入", "需求不准会导致返工", "总体设计约束后续实现"],
        }

    diagram_section = _section_body(answer_text, "二")
    terms = _extract_terms(diagram_section, limit=8)
    if len(terms) < 4:
        terms = (terms + ["核心概念", "输入条件", "处理过程", "输出结果", "常见误区", "应用场景"])[:6]
    return {
        "title": _shorten(question, 24) or "知识点关系图",
        "subtitle": "核心观点：先抓主线，再展开细节",
        "flow": [(term, "知识点") for term in terms[:6]],
        "left": {"title": "前提 / 输入", "color": "#2563eb", "items": terms[:4]},
        "right": {"title": "结果 / 输出", "color": "#0ea5e9", "items": terms[4:8] or terms[2:6]},
        "relations": ["概念到判断", "输入到输出", "流程到产物", "误区到纠正"],
    }


def _wrap_svg_text(text: str, max_chars: int = 10, max_lines: int = 2) -> list[str]:
    content = re.sub(r"\s+", "", str(text or "").strip())
    if not content:
        return []
    lines = [content[index : index + max_chars] for index in range(0, len(content), max_chars)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1] + "…"
    return lines


def _svg_text(x: int, y: int, text: str, size: int = 18, color: str = "#0f172a", weight: int = 700, anchor: str = "middle", max_chars: int = 10) -> str:
    lines = _wrap_svg_text(text, max_chars=max_chars, max_lines=2)
    start_y = y if len(lines) == 1 else y - 10
    return "".join(
        f'<text x="{x}" y="{start_y + index * 22}" text-anchor="{anchor}" '
        f'font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}">{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def _build_diagram_image(answer_text: str, question: str) -> str:
    model = _diagram_model(answer_text, question)
    width, height = 1200, 720
    flow = model["flow"][:6]
    relations = model["relations"][:4]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="#f8fbff"/><stop offset="100%" stop-color="#eaf4ff"/></linearGradient>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#2563eb" flood-opacity="0.13"/></filter>',
        '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M2,2 L10,6 L2,10 Z" fill="#60a5fa"/></marker>',
        "</defs>",
        '<rect width="1200" height="720" rx="30" fill="url(#bg)"/>',
        '<rect x="44" y="38" width="1112" height="644" rx="28" fill="#ffffff" stroke="#bfdbfe" stroke-width="2"/>',
        f'<text x="600" y="86" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="33" font-weight="800" fill="#1d4ed8">{html.escape(model["title"])}</text>',
        f'<text x="600" y="120" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="18" fill="#64748b">{html.escape(model["subtitle"])}</text>',
    ]

    start_x, flow_y = 84, 180
    gap, box_w, box_h = 178, 150, 78
    for index, (title, desc) in enumerate(flow):
        x = start_x + index * gap
        fill = "#eff6ff" if index % 2 == 0 else "#e0f2fe"
        svg.append(f'<rect x="{x}" y="{flow_y}" width="{box_w}" height="{box_h}" rx="18" fill="{fill}" stroke="#60a5fa" stroke-width="2" filter="url(#shadow)"/>')
        svg.append(_svg_text(x + box_w // 2, flow_y + 35, title, size=17, color="#0f3a78", weight=800, max_chars=8))
        svg.append(_svg_text(x + box_w // 2, flow_y + 62, desc, size=12, color="#64748b", weight=600, max_chars=10))
        if index < len(flow) - 1:
            x1 = x + box_w + 8
            x2 = start_x + (index + 1) * gap - 10
            svg.append(f'<line x1="{x1}" y1="{flow_y + box_h // 2}" x2="{x2}" y2="{flow_y + box_h // 2}" stroke="#60a5fa" stroke-width="3" marker-end="url(#arrow)"/>')

    for x, y, panel in [(86, 330, model["left"]), (642, 330, model["right"])]:
        svg.append(f'<rect x="{x}" y="{y}" width="472" height="190" rx="22" fill="#f8fbff" stroke="#bfdbfe" stroke-width="2"/>')
        svg.append(f'<circle cx="{x + 36}" cy="{y + 38}" r="13" fill="{panel["color"]}"/>')
        svg.append(f'<text x="{x + 60}" y="{y + 46}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="24" font-weight="800" fill="#0f3a78">{html.escape(panel["title"])}</text>')
        for idx, item in enumerate(panel["items"][:4]):
            row_y = y + 82 + idx * 27
            svg.append(f'<rect x="{x + 30}" y="{row_y - 17}" width="14" height="14" rx="4" fill="{panel["color"]}" opacity="0.8"/>')
            svg.append(f'<text x="{x + 56}" y="{row_y - 5}" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="17" font-weight="650" fill="#1e293b">{html.escape(_shorten(item, 24))}</text>')

    svg.append('<line x1="558" y1="425" x2="642" y2="425" stroke="#60a5fa" stroke-width="4" marker-end="url(#arrow)"/>')
    svg.append('<text x="600" y="410" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="15" font-weight="800" fill="#2563eb">前后衔接</text>')
    svg.append('<rect x="86" y="565" width="1028" height="70" rx="18" fill="#eff6ff" stroke="#bfdbfe" stroke-width="2"/>')
    svg.append('<text x="118" y="607" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="19" font-weight="800" fill="#1d4ed8">关系链</text>')
    for index, relation in enumerate(relations):
        svg.append(f'<text x="{220 + index * 225}" y="607" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="16" font-weight="650" fill="#0f172a">{html.escape(_shorten(relation, 18))}</text>')

    svg.append("</svg>")
    encoded = base64.b64encode("".join(svg).encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


@chat_bp.post("/answer")
@login_required
def answer():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        question = _clean_text(payload["question"])
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
        answer_text = _clean_text(result["answer"], "当前回答编码异常，请重新生成一次。")
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
