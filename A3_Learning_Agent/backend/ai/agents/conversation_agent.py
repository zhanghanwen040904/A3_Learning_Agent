import json
import re
from typing import Any, Dict, List

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.llm_adapter import PlatformLLM
from ai.langchain_parsers import parse_json_with_fallback
from ai.rag import retrieve_knowledge, retrieve_knowledge_items


CHAT_PROMPT_TEMPLATE = """
你是高校课程学习助手。你的首要任务是认真回答学生当前这条问题，而不是追问画像。

请严格遵守：
- 优先直接解决用户当前问题，像主流大模型一样自然回答。
- 不要说“我已经理解了你的问题”“我会更新画像”这类空话。
- 不要主动追问画像信息。
- 若知识库里有相关证据，优先结合证据回答；若证据不足，也要基于常识给出清晰回答，并明确哪些部分来自课程知识、哪些是一般学习建议。
- 回答尽量结构清晰，但不要僵硬。
- 如果用户明确要求“图解/流程图/结构梳理/示意图”，need_diagram 设为 true。
- 如果用户要求图解，assistant_reply 里不要输出字符画、ASCII 框图、表格图、伪图形排版，不要使用 `|`、`┌`、`└`、`—` 这类文本拼图。
- 如果用户要求图解，assistant_reply 只需要给出“1个主题 + 3到4个核心点 + 每点一句解释”的纯文字结构，便于前端生成真正图解。
- 如果用户明确要求“出题/练习/自测/巩固”，need_quiz 设为 true。

你必须只返回 JSON，不要返回 markdown，不要解释：
{{
  "assistant_reply": "",
  "need_diagram": false,
  "need_quiz": false
}}

当前用户问题：
{question}

最近对话（供你理解上下文）：
{messages}

课程知识库证据：
{evidence}
""".strip()


QUIZ_PROMPT_TEMPLATE = """
你是课程助教。请基于下面的回答内容，生成 2 道简短巩固题。

要求：
- 只返回 JSON，不要解释。
- 格式必须是：
{{
  "quiz_items": [
    {{"question": "", "answer_hint": ""}},
    {{"question": "", "answer_hint": ""}}
  ]
}}

当前回答内容：
{answer}
""".strip()


CHAT_PROMPT = LangChainPromptTemplate.from_template(CHAT_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None
QUIZ_PROMPT = LangChainPromptTemplate.from_template(QUIZ_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class ConversationAgent:
    def __init__(self):
        self.chat_chain = (CHAT_PROMPT | PlatformLLM() | LangChainStrOutputParser()) if CHAT_PROMPT is not None and LangChainStrOutputParser is not None else None
        self.quiz_chain = (QUIZ_PROMPT | PlatformLLM() | LangChainStrOutputParser()) if QUIZ_PROMPT is not None and LangChainStrOutputParser is not None else None

    def respond(self, messages: List[Dict[str, Any]], current_profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
        question = self._latest_user_message(messages)
        evidence_items = retrieve_knowledge_items(question, top_k=4)
        evidence = retrieve_knowledge(question, top_k=4)
        need_diagram = self._question_wants_diagram(question)
        need_quiz = self._question_wants_quiz(question)

        raw = self._invoke_chat(
            {
                "question": question,
                "messages": json.dumps(messages[-12:], ensure_ascii=False),
                "evidence": evidence or "未检索到直接证据",
            }
        )

        if self._is_error_payload(raw):
            return self._fallback_result(question, evidence_items, evidence, "当前大模型服务暂时异常，请稍后重试。")

        data = parse_json_with_fallback(raw)
        assistant_reply = self._clean_reply(data.get("assistant_reply"))
        if not assistant_reply:
            assistant_reply = self._fallback_answer(question, evidence)
        if need_diagram:
            assistant_reply = self._normalize_diagram_reply(question, assistant_reply, evidence)
        need_quiz = need_quiz or self._should_offer_quiz(question, assistant_reply)

        return {
            "assistant_reply": assistant_reply,
            "need_diagram": bool(data.get("need_diagram")) or need_diagram,
            "need_quiz": bool(data.get("need_quiz")) or need_quiz,
            "diagram_image": "",
            "quiz_items": [],
            "sources": evidence_items,
        }

    def enhance(
        self,
        messages: List[Dict[str, Any]],
        answer: str,
        profile: Dict[str, Any] | None = None,
        need_diagram: bool = False,
        need_quiz: bool = False,
    ) -> Dict[str, Any]:
        quiz_items: List[Dict[str, str]] = []
        if need_quiz:
            quiz_items = self._generate_quiz_items(answer)
        return {
            "diagram_image": "",
            "quiz_items": quiz_items,
            "need_diagram": bool(need_diagram),
            "need_quiz": bool(need_quiz),
        }

    def _invoke_chat(self, variables: Dict[str, Any]) -> str:
        if self.chat_chain is not None:
            return self.chat_chain.invoke(variables)
        return PlatformLLM().invoke(CHAT_PROMPT_TEMPLATE.format(**variables))

    def _generate_quiz_items(self, answer: str) -> List[Dict[str, str]]:
        variables = {"answer": answer[:4000]}
        try:
            raw = self.quiz_chain.invoke(variables) if self.quiz_chain is not None else PlatformLLM().invoke(QUIZ_PROMPT_TEMPLATE.format(**variables))
            if self._is_error_payload(raw):
                return self._fallback_quiz_items(answer)
            data = parse_json_with_fallback(raw)
            items = data.get("quiz_items")
            if isinstance(items, list):
                normalized = []
                for item in items[:3]:
                    if not isinstance(item, dict):
                        continue
                    question = str(item.get("question") or "").strip()
                    answer_hint = str(item.get("answer_hint") or "").strip()
                    if question:
                        normalized.append({"question": question, "answer_hint": answer_hint})
                if normalized:
                    return normalized
        except Exception:
            pass
        return self._fallback_quiz_items(answer)

    def _fallback_result(self, question: str, sources: List[Dict[str, Any]], evidence: str, message: str) -> Dict[str, Any]:
        return {
            "assistant_reply": f"{message}\n\n你也可以稍后重试，或者把问题描述得更具体一些，我会继续帮你。",
            "need_diagram": self._question_wants_diagram(question),
            "need_quiz": self._question_wants_quiz(question),
            "diagram_image": "",
            "quiz_items": [],
            "sources": sources,
        }

    def _fallback_answer(self, question: str, evidence: str) -> str:
        text = str(evidence or "").strip()
        if text:
            excerpt = re.sub(r"\n{2,}", "\n", text)[:360]
            return f"我先结合课程知识库回答你：\n\n{excerpt}\n\n如果你愿意，我也可以继续把这个问题拆成更容易理解的步骤。"
        return f"我可以继续帮你分析“{question}”。如果你希望，我可以把它拆成概念、流程、例子三个层次来讲。"

    def _fallback_quiz_items(self, answer: str) -> List[Dict[str, str]]:
        return [
            {"question": "请用一句话复述这段回答中的核心结论。", "answer_hint": "先说最关键的概念或判断。"},
            {"question": "如果把这个知识点放到实际课程题目里，最容易混淆的地方是什么？", "answer_hint": "可以从概念边界、步骤顺序或输入输出去想。"},
        ]

    def _latest_user_message(self, messages: List[Dict[str, Any]]) -> str:
        for item in reversed(messages or []):
            if item.get("role") == "user":
                return str(item.get("content") or "").strip()
        return ""

    def _is_error_payload(self, text: Any) -> bool:
        try:
            data = json.loads(str(text or ""))
        except Exception:
            return False
        return isinstance(data, dict) and data.get("success") is False and bool(data.get("error"))

    def _clean_reply(self, text: Any) -> str:
        content = str(text or "").replace("\r", "").strip()
        if not content:
            return ""
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"[|┌┐└┘├┤┬┴─━═]+", " ", content)
        content = re.sub(r"\n\s*\n", "\n\n", content)
        content = re.sub(r"\n[ \t]+\n", "\n\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r"[ \t]+\n", "\n", content)
        return content.strip()

    def _normalize_diagram_reply(self, question: str, reply: str, evidence: str) -> str:
        title = self._diagram_title(question, reply)
        points = self._diagram_points(reply, evidence)
        lines = [f"{title}", "", "核心主线：按知识结构来理解这个问题。", ""]
        for idx, item in enumerate(points[:4], start=1):
            lines.append(f"{idx}. {item['title']}：{item['desc']}")
        return "\n".join(lines).strip()

    def _diagram_title(self, question: str, reply: str) -> str:
        text = f"{question}\n{reply}"
        patterns = [
            r"Scrum冲刺[（(]?\s*Sprint\s*[)）]?",
            r"Sprint时间盒",
            r"Sprint",
            r"软件生命周期",
            r"需求分析",
            r"总体设计",
            r"详细设计",
            r"软件测试",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return f"{match.group(0)} 图解"
        q = re.sub(r"[？?。！!\s]", "", question)
        return f"{q[:16] or '知识点'} 图解"

    def _diagram_points(self, reply: str, evidence: str) -> List[Dict[str, str]]:
        source = self._clean_reply(reply)
        source = re.sub(r"[|┌┐└┘├┤┬┴─━═]+", " ", source)
        source = re.sub(r"\[[^\]]{1,20}\]", "", source)
        source = re.sub(r"[↑↓←→►▶]+", " ", source)
        candidates: List[Dict[str, str]] = []

        for line in source.splitlines():
            line = line.strip(" -*•○\t")
            if not line or len(line) < 4:
                continue
            if "：" in line or ":" in line:
                parts = re.split(r"[：:]", line, maxsplit=1)
                title = self._short_text(parts[0], 12)
                desc = self._short_text(parts[1], 34)
                if self._valid_diagram_title(title) and desc:
                    candidates.append({"title": title, "desc": desc})

        if len(candidates) >= 3:
            return candidates[:4]

        evidence_lines = [item.strip() for item in str(evidence or "").splitlines() if item.strip()]
        for line in evidence_lines:
            parts = re.split(r"[：:；;。]", line, maxsplit=1)
            title = self._short_text(parts[0], 12)
            desc = self._short_text(parts[1] if len(parts) > 1 else line, 34)
            if self._valid_diagram_title(title):
                candidates.append({"title": title, "desc": desc})
            if len(candidates) >= 4:
                break

        deduped = []
        seen = set()
        for item in candidates:
            key = item["title"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        if len(deduped) >= 3:
            return deduped[:4]

        fallback = [
            {"title": "时间长度", "desc": "Sprint 通常是固定时长的小周期迭代，长度不能随意延长。"},
            {"title": "核心事件", "desc": "常见包括计划会、每日站会、评审会和回顾会。"},
            {"title": "关键产出", "desc": "每个 Sprint 都应产出一个可检查、可交付的增量结果。"},
            {"title": "本质特点", "desc": "强调短周期、快速反馈、持续改进和连续推进。"},
        ]
        return fallback

    def _valid_diagram_title(self, title: str) -> bool:
        if not title or len(title) < 2:
            return False
        invalid_parts = ["可以", "以下", "文字版", "示意图", "直接手绘", "该图", "对应教材", "建议用"]
        return not any(part in title for part in invalid_parts)

    def _short_text(self, text: str, limit: int) -> str:
        content = re.sub(r"\s+", "", str(text or ""))
        content = re.sub(r"[*_`#\[\]【】（）()]", "", content)
        return content[:limit]

    def _question_wants_diagram(self, question: str) -> bool:
        return any(token in question for token in ["图解", "画图", "流程图", "结构图", "示意图", "梳理一下", "可视化"])

    def _question_wants_quiz(self, question: str) -> bool:
        return any(token in question for token in ["出题", "练习", "自测", "测试题", "刷题", "巩固题"])

    def _should_offer_quiz(self, question: str, answer: str) -> bool:
        question_text = str(question or "").strip()
        answer_text = str(answer or "").strip()
        if not answer_text or len(answer_text) < 80:
            return False

        # 用户若只是寒暄、泛指令或简单确认，一般不追加巩固题。
        low_signal_patterns = [
            "你好", "在吗", "谢谢", "好的", "收到", "继续", "展开讲讲", "再说一遍"
        ]
        if any(token == question_text for token in low_signal_patterns):
            return False

        teaching_question_tokens = [
            "是什么", "为什么", "怎么理解", "区别", "联系", "阶段", "流程",
            "步骤", "原理", "作用", "特点", "生命周期", "如何"
        ]
        teaching_answer_tokens = [
            "可以分为", "主要包括", "核心是", "关键在于", "本质上", "通常分为",
            "第一", "第二", "第三", "例如", "区别在于", "可以理解为", "常见做法"
        ]

        is_teaching_question = any(token in question_text for token in teaching_question_tokens)
        has_teaching_structure = any(token in answer_text for token in teaching_answer_tokens)
        has_ordered_structure = bool(re.search(r"(\n|^)\s*(\d+[\.、]|[-•○])\s*", answer_text))

        # 只在明显是讲解型回答时自动补巩固，避免每次都打断对话。
        return is_teaching_question and (has_teaching_structure or has_ordered_structure)
