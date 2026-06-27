import json
import re
from typing import Any, Dict, List, Optional

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.langchain_adapter import SparkLLM
from ai.langchain_parsers import parse_json_with_fallback
from config import config
from .base_agent import XunfeiAgentSpec

PROFILE_FIELDS = [
    "major",
    "target_course",
    "knowledge_level",
    "study_style",
    "weak_points",
    "study_goal",
    "study_time_prefer",
    "course_progress",
    "challenge_scene",
    "preferred_resource",
    "profile_summary",
]

DEFAULT_VALUE = "待进一步观察"

FIELD_ALIASES = {
    "major": ["专业背景", "专业", "方向"],
    "target_course": ["目标课程", "课程", "章节"],
    "knowledge_level": ["基础情况", "知识基础", "基础水平"],
    "study_style": ["学习方式", "学习风格", "学习偏好"],
    "weak_points": ["知识短板", "薄弱点", "不会", "容易卡住"],
    "study_goal": ["学习目标", "目标", "希望达到"],
    "study_time_prefer": ["时间偏好", "学习时间", "效率最高"],
    "course_progress": ["课程进度", "学到哪里", "当前进度"],
    "challenge_scene": ["困难场景", "最常卡住", "跟不上"],
    "preferred_resource": ["资源偏好", "想优先看到", "喜欢的资源"],
}

PROFILE_ANALYZE_PROMPT_TEMPLATE = """
你是学习画像分析师。请从学生自然语言对话中抽取结构化学习画像。
必须严格只返回 JSON，不要 markdown，不要解释。
JSON 字段必须完全一致：
{{"major":"","target_course":"","knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":"","challenge_scene":"","preferred_resource":"","profile_summary":""}}

字段要求：
- major：学生专业或方向
- target_course：本次主要学习课程或章节
- knowledge_level：当前基础水平
- study_style：偏好的学习方式
- weak_points：当前薄弱知识点
- study_goal：希望达到的结果
- study_time_prefer：时间偏好与学习节奏
- course_progress：当前课程进度
- challenge_scene：最常卡住的场景
- preferred_resource：偏好的资源类型
- profile_summary：用 1 句话概括学生画像

如果信息不足，请根据对话合理归纳为“{default_value}”，不要增加新字段。

学生对话：
{dialogue_text}
""".strip()

PROFILE_CHAT_PROMPT_TEMPLATE = """
你是高校课程个性化学习画像智能体。你正在和学生进行自然语言对话式画像构建。
请根据【完整多轮对话】和【当前画像草稿】，完成三件事：
1. 自动抽取或更新结构化学生画像，不要只机械复制最后一句，要综合上下文理解；
2. 判断哪些画像维度仍然缺失或模糊；
3. 生成下一轮最有价值的自然语言追问。若画像已经足够完整，则 next_question 给出确认语，引导用户点击“生成画像”。

必须严格只返回 JSON，不要 markdown，不要解释。JSON 字段必须完全一致：
{{
  "profile": {{"major":"","target_course":"","knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":"","challenge_scene":"","preferred_resource":"","profile_summary":""}},
  "missing_fields": [],
  "next_question": "",
  "confidence": 0.0,
  "is_complete": false,
  "reasoning_note": ""
}}

追问策略：
- 不要重复询问学生已经明确说过的信息；
- 如果学生一句话包含多个维度，要一次性抽取多个字段；
- 如果回答模糊，例如“公式都不会”，要追问是哪类公式、哪个课程环节；
- 每次只问 1 个最关键问题，语气自然简洁；
- 至少 6 个核心维度清晰后，is_complete 才可为 true。

当前画像草稿：
{base_profile}

完整多轮对话：
{messages}
""".strip()

PROFILE_ANALYZE_PROMPT = LangChainPromptTemplate.from_template(PROFILE_ANALYZE_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None
PROFILE_CHAT_PROMPT = LangChainPromptTemplate.from_template(PROFILE_CHAT_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class ProfileAgent:
    """从学生对话中提取结构化学习画像。"""

    def __init__(self):
        self.role = "学习画像分析师"
        self.goal = "从学生自然语言对话中抽取学习画像，并严格返回 JSON。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["langchain_prompt", "spark_llm"],
            input_schema="学生自然语言对话文本",
            output_schema='{"major":"","target_course":"","knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":"","challenge_scene":"","preferred_resource":"","profile_summary":""}',
        )
        self.analyze_chain = (PROFILE_ANALYZE_PROMPT | SparkLLM() | LangChainStrOutputParser()) if PROFILE_ANALYZE_PROMPT is not None and LangChainStrOutputParser is not None else None
        self.chat_chain = (PROFILE_CHAT_PROMPT | SparkLLM() | LangChainStrOutputParser()) if PROFILE_CHAT_PROMPT is not None and LangChainStrOutputParser is not None else None

    def analyze(self, dialogue_text: str) -> Dict[str, str]:
        parsed = self._extract_from_dialogue(dialogue_text)
        if config.MOCK_AI:
            return parsed

        variables = {"default_value": DEFAULT_VALUE, "dialogue_text": dialogue_text}
        if self.analyze_chain is not None:
            raw = self.analyze_chain.invoke(variables)
        else:
            raw = SparkLLM().invoke(PROFILE_ANALYZE_PROMPT_TEMPLATE.format(**variables))
        model_result = self._parse_profile(raw)
        return self._merge_profile(model_result, parsed)

    def _parse_profile(self, raw: str) -> Dict[str, str]:
        data = parse_json_with_fallback(raw)
        return {field: str(data.get(field) or DEFAULT_VALUE) for field in PROFILE_FIELDS}

    def chat_extract(self, messages: List[Dict[str, str]], current_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """基于完整多轮对话，调用大模型动态抽取画像并生成下一轮追问。"""
        current_profile = current_profile or {}
        parsed_from_messages = self._extract_from_dialogue(self._messages_to_dialogue(messages))
        base_profile = self._normalize_profile({**current_profile, **{k: v for k, v in parsed_from_messages.items() if v != DEFAULT_VALUE}})

        if config.MOCK_AI:
            return self._build_chat_result(base_profile, source="mock_fallback")

        variables = {
            "base_profile": json.dumps(base_profile, ensure_ascii=False),
            "messages": json.dumps(messages, ensure_ascii=False),
        }
        if self.chat_chain is not None:
            raw = self.chat_chain.invoke(variables)
        else:
            raw = SparkLLM().invoke(PROFILE_CHAT_PROMPT_TEMPLATE.format(**variables))
        data = parse_json_with_fallback(raw)
        model_profile = self._normalize_profile(data.get("profile") or {})
        merged_profile = self._merge_profile(model_profile, base_profile)
        missing_fields = self._missing_fields(merged_profile)
        next_question = str(data.get("next_question") or self._next_question_for_missing(missing_fields)).strip()
        is_complete = bool(data.get("is_complete")) and len(missing_fields) <= 4
        if not next_question:
            next_question = self._next_question_for_missing(missing_fields)
        if is_complete and missing_fields:
            next_question = "画像已经基本完整。你也可以继续补充学习历史、考试时间或资源偏好，或者直接点击“生成画像”。"
        confidence = data.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = self._confidence_by_profile(merged_profile)
        return {
            "profile": merged_profile,
            "missing_fields": missing_fields,
            "next_question": next_question,
            "confidence": max(0.0, min(1.0, confidence)),
            "is_complete": is_complete or len(missing_fields) <= 4,
            "reasoning_note": str(data.get("reasoning_note") or "已由讯飞星火大模型基于多轮上下文完成语义抽取与动态追问。"),
            "model_enabled": True,
            "source": "spark_chat",
        }

    def _normalize_profile(self, profile: Dict[str, Any]) -> Dict[str, str]:
        normalized = {}
        for field in PROFILE_FIELDS:
            value = str(profile.get(field) or DEFAULT_VALUE).strip()
            normalized[field] = value or DEFAULT_VALUE
        normalized["profile_summary"] = self._build_summary(normalized)
        return normalized

    def _messages_to_dialogue(self, messages: List[Dict[str, str]]) -> str:
        lines = []
        for item in messages or []:
            role = "学生" if item.get("role") == "user" else "画像助手"
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role}：{content}")
        return "\n".join(lines)

    def _missing_fields(self, profile: Dict[str, str]) -> List[str]:
        return [field for field in PROFILE_FIELDS if field != "profile_summary" and (not profile.get(field) or profile.get(field) == DEFAULT_VALUE)]

    def _confidence_by_profile(self, profile: Dict[str, str]) -> float:
        filled = len([field for field in PROFILE_FIELDS if field != "profile_summary" and profile.get(field) and profile.get(field) != DEFAULT_VALUE])
        return round(filled / max(len(PROFILE_FIELDS) - 1, 1), 2)

    def _next_question_for_missing(self, missing_fields: List[str]) -> str:
        questions = {
            "major": "你现在的专业或主要学习方向是什么？",
            "target_course": "这次你主要想围绕哪门课程或哪个章节来学习？",
            "knowledge_level": "你目前对这门课的基础大概如何？哪些内容已经掌握，哪些还不稳定？",
            "weak_points": "你现在最容易卡住的知识点或题型是什么？可以举一个具体例子。",
            "study_goal": "你希望在什么时间内达到什么学习结果？例如考试、作业、实验或项目。",
            "study_style": "你更喜欢哪种学习方式？比如图解、案例、视频、代码实操或分层练习。",
            "study_time_prefer": "你每天大概能投入多久学习？通常哪个时间段效率更高？",
            "course_progress": "这门课你目前学到哪里了？有没有作业、实验或考试节点？",
            "challenge_scene": "你通常在哪种学习场景最困难？例如看公式、做题、写代码或听课跟不上。",
            "preferred_resource": "后续生成资源时，你最希望优先看到哪几类学习材料？",
        }
        for field in missing_fields:
            if field in questions:
                return questions[field]
        return "画像已经基本完整。你可以继续补充特殊需求，或者点击“生成画像”保存。"

    def _build_chat_result(self, profile: Dict[str, str], source: str) -> Dict[str, Any]:
        missing_fields = self._missing_fields(profile)
        return {
            "profile": profile,
            "missing_fields": missing_fields,
            "next_question": self._next_question_for_missing(missing_fields),
            "confidence": self._confidence_by_profile(profile),
            "is_complete": len(missing_fields) <= 4,
            "reasoning_note": "当前为 MOCK_AI 演示模式，使用本地语义兜底模拟大模型画像抽取；正式评测请配置讯飞星火并关闭 MOCK_AI。",
            "model_enabled": False,
            "source": source,
        }

    def _merge_profile(self, model_result: Dict[str, str], parsed: Dict[str, str]) -> Dict[str, str]:
        merged = {}
        for field in PROFILE_FIELDS:
            parsed_value = parsed.get(field) or DEFAULT_VALUE
            model_value = model_result.get(field) or DEFAULT_VALUE
            merged[field] = parsed_value if parsed_value != DEFAULT_VALUE else model_value
        merged["profile_summary"] = self._build_summary(merged)
        return merged

    def _extract_from_dialogue(self, dialogue_text: str) -> Dict[str, str]:
        text = str(dialogue_text or "").strip()
        result = {field: DEFAULT_VALUE for field in PROFILE_FIELDS}
        if not text:
            return result

        for field, aliases in FIELD_ALIASES.items():
            result[field] = self._extract_by_aliases(text, aliases)

        if result["major"] == DEFAULT_VALUE:
            result["major"] = self._guess_major(text)
        if result["target_course"] == DEFAULT_VALUE:
            result["target_course"] = self._guess_course(text)
        if result["knowledge_level"] == DEFAULT_VALUE:
            result["knowledge_level"] = self._guess_knowledge_level(text)
        if result["study_style"] == DEFAULT_VALUE:
            result["study_style"] = self._guess_style(text)
        if result["preferred_resource"] == DEFAULT_VALUE:
            result["preferred_resource"] = self._guess_resource(text)
        if result["study_time_prefer"] == DEFAULT_VALUE:
            result["study_time_prefer"] = self._guess_time(text)
        if result["study_goal"] == DEFAULT_VALUE:
            result["study_goal"] = self._guess_goal(text)
        if result["weak_points"] == DEFAULT_VALUE:
            result["weak_points"] = self._guess_weak_point(text)
        if result["challenge_scene"] == DEFAULT_VALUE:
            result["challenge_scene"] = self._guess_challenge_scene(text)

        result["profile_summary"] = self._build_summary(result)
        return result

    def _extract_by_aliases(self, text: str, aliases: List[str]) -> str:
        for alias in aliases:
            match = re.search(rf"{re.escape(alias)}[：:\s]+(.+)", text)
            if match:
                value = match.group(1).strip().splitlines()[0].strip()
                return value or DEFAULT_VALUE
        return DEFAULT_VALUE


    def _normalize_choice_text(self, text: str) -> str:
        normalized = str(text or "")
        compact = re.sub(r"\s+", "", normalized)
        option_map = {
            "A": "\u56fe\u6587\u8bb2\u89e3",
            "\uff21": "\u56fe\u6587\u8bb2\u89e3",
            "B": "\u4ee3\u7801\u793a\u4f8b",
            "\uff22": "\u4ee3\u7801\u793a\u4f8b",
            "C": "\u601d\u7ef4\u5bfc\u56fe",
            "\uff23": "\u601d\u7ef4\u5bfc\u56fe",
            "D": "\u5176\u4ed6\u65b9\u5f0f",
            "\uff24": "\u5176\u4ed6\u65b9\u5f0f",
        }
        # Only treat A/B/C/D as option answers when the user explicitly chooses one,
        # instead of replacing every option label shown in the question text.
        for key, value in option_map.items():
            choose_pattern = rf"(?:\u9009\u62e9|\u9009|\u6211\u9009|\u6211\u9009\u62e9){re.escape(key)}(?:$|[\u3002\uff0c,.;\s])"
            tail_pattern = rf"(?:^|[\n\r\u6211\uff1a:]){re.escape(key)}$"
            if re.search(choose_pattern, compact) or re.search(tail_pattern, compact):
                return value
        if re.fullmatch(r"[A-D\uff21-\uff24]", compact):
            return option_map.get(compact, normalized)
        return normalized

    def _guess_major(self, text: str) -> str:
        # Prefer the explicit major phrase before generic course names.
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z0-9]+(?:\u4e0e\u6280\u672f|\u79d1\u5b66|\u5de5\u7a0b|\u4e13\u4e1a))\u4e13\u4e1a\u5b66\u751f",
            r"\u6211\u662f([\u4e00-\u9fa5A-Za-z0-9]+)\u4e13\u4e1a",
            r"\u4e13\u4e1a[\u662f\u4e3a:\uff1a\s]+([\u4e00-\u9fa5A-Za-z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                value = re.sub(r"^(?:\u6211\u662f|\u6211|\u672c\u4eba\u662f)", "", value)
                value = re.sub(r"\u5b66\u751f$", "", value)
                return value or DEFAULT_VALUE

        candidates = [
            "\u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f",
            "\u8ba1\u7b97\u673a\u79d1\u5b66",
            "\u4eba\u5de5\u667a\u80fd",
            "\u8ba1\u7b97\u673a",
            "\u6570\u636e\u79d1\u5b66",
            "\u7f51\u7edc\u5de5\u7a0b",
            "\u81ea\u52a8\u5316",
            "\u8f6f\u4ef6\u5de5\u7a0b",
        ]
        for item in candidates:
            if item in text:
                # If software engineering is used as a course, do not overwrite the student's major.
                if item == "\u8f6f\u4ef6\u5de5\u7a0b" and re.search(r"\u8f6f\u4ef6\u5de5\u7a0b(?:\u8bfe|\u8bfe\u7a0b|\u7ae0\u8282)", text):
                    continue
                return item
        return DEFAULT_VALUE

    def _guess_course(self, text: str) -> str:
        course_patterns = [
            r"\u5b66\u4e60([\u4e00-\u9fa5A-Za-z0-9]+?)\u8bfe\u7a0b",
            r"\u9488\u5bf9([\u4e00-\u9fa5A-Za-z0-9]+?)\u8bfe",
            r"\u8bfe\u7a0b[\u662f\u4e3a:\uff1a\s]+([\u4e00-\u9fa5A-Za-z0-9]+)",
        ]
        for pattern in course_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if "\u8f6f\u4ef6\u5de5\u7a0b" in text:
            return "\u8f6f\u4ef6\u5de5\u7a0b"
        candidates = ["\u9700\u6c42\u5206\u6790", "\u53ef\u884c\u6027\u7814\u7a76", "\u603b\u4f53\u8bbe\u8ba1", "\u8be6\u7ec6\u8bbe\u8ba1", "\u8f6f\u4ef6\u6d4b\u8bd5", "\u8f6f\u4ef6\u7ef4\u62a4", "\u8f6f\u4ef6\u751f\u547d\u5468\u671f", "\u7ed3\u6784\u5316\u8bbe\u8ba1"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_knowledge_level(self, text: str) -> str:
        if any(item in text for item in ["\u5f88\u591a\u5b9a\u4e49\u4e0d\u592a\u4f1a", "\u5f88\u591a\u5b9a\u4e49\u4e0d\u4f1a", "\u5b9a\u4e49\u4e0d\u592a\u4f1a", "\u5b9a\u4e49\u4e0d\u4f1a"]):
            return "\u5b9a\u4e49\u7406\u89e3\u8584\u5f31"
        candidates = ["\u96f6\u57fa\u7840", "\u521a\u5165\u95e8", "\u57fa\u7840\u8584\u5f31", "\u57fa\u7840\u8f83\u5f31", "\u57fa\u7840\u4e00\u822c", "\u57fa\u7840\u4e0d\u592a\u597d", "\u57fa\u7840\u4e0d\u597d", "\u4e00\u822c", "\u8fd8\u53ef\u4ee5", "\u6709\u4e00\u5b9a\u57fa\u7840", "\u57fa\u7840\u8f83\u597d", "\u6bd4\u8f83\u719f\u6089", "\u638c\u63e1\u8f83\u597d"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_style(self, text: str) -> str:
        normalized = self._normalize_choice_text(text)
        # Extract the resource or style exactly when user writes it in natural language.
        explicit = ["\u56fe\u6587\u8bb2\u89e3", "\u4ee3\u7801\u793a\u4f8b", "\u601d\u7ef4\u5bfc\u56fe", "\u56fe\u89e3", "\u6848\u4f8b", "\u5206\u5c42\u7ec3\u4e60", "\u89c6\u9891", "\u4ee3\u7801\u5b9e\u64cd", "\u8bb2\u89e3"]
        tags = [item for item in explicit if item in normalized]
        if "\u56fe\u6587\u8bb2\u89e3" in tags:
            tags = [item for item in tags if item not in {"\u56fe\u89e3", "\u8bb2\u89e3"}]
        return "\u3001".join(tags[:3]) if tags else DEFAULT_VALUE

    def _guess_resource(self, text: str) -> str:
        normalized = self._normalize_choice_text(text)
        explicit = ["\u56fe\u6587\u8bb2\u89e3", "\u4ee3\u7801\u793a\u4f8b", "\u601d\u7ef4\u5bfc\u56fe", "\u8bb2\u89e3\u6587\u6863", "\u7ec3\u4e60\u9898", "\u4ee3\u7801\u6848\u4f8b", "\u89c6\u9891", "\u62d3\u5c55\u9605\u8bfb", "\u56fe\u89e3"]
        tags = [item for item in explicit if item in normalized]
        if "\u56fe\u6587\u8bb2\u89e3" in tags:
            tags = [item for item in tags if item not in {"\u56fe\u89e3"}]
        return "\u3001".join(tags[:3]) if tags else DEFAULT_VALUE

    def _guess_time(self, text: str) -> str:
        parts = []
        if re.search(r"\u665a\u4e0a\s*12\s*\u70b9|12\s*\u70b9", text):
            parts.append("\u665a\u4e0a12\u70b9")
        parts.extend(item for item in ["\u665a\u4e0a", "\u767d\u5929", "\u5468\u672b", "\u788e\u7247\u65f6\u95f4", "60\u5206\u949f", "1\u5c0f\u65f6", "\u4e24\u5c0f\u65f6"] if item in text and item not in parts)
        return "\u3001".join(parts) if parts else DEFAULT_VALUE

    def _guess_goal(self, text: str) -> str:
        score = re.search(r"(?:\u62ff\u5230|\u8003\u5230|\u8fbe\u5230)?\s*(\d{2,3})\s*\u5206", text)
        if score:
            return f"\u62ff\u5230{score.group(1)}\u5206"
        return DEFAULT_VALUE

    def _guess_weak_point(self, text: str) -> str:
        candidates = ["\u7011\u5e03\u6a21\u578b", "\u9700\u6c42\u5206\u6790", "\u53ef\u884c\u6027\u7814\u7a76", "\u603b\u4f53\u8bbe\u8ba1", "\u8be6\u7ec6\u8bbe\u8ba1", "\u8f6f\u4ef6\u6d4b\u8bd5", "\u8f6f\u4ef6\u7ef4\u62a4", "\u8f6f\u4ef6\u751f\u547d\u5468\u671f", "\u6570\u636e\u6d41\u56fe", "\u6a21\u5757\u8bbe\u8ba1", "\u7f16\u7801\u5b9e\u73b0", "\u6570\u636e\u5b57\u5178"]
        hits = [item for item in candidates if item in text]
        if hits:
            suffix = "\u76f8\u5173\u6a21\u578b" if "\u6a21\u578b" in text and not hits[0].endswith("\u6a21\u578b") else ""
            return "\u3001".join(hits[:4]) + suffix
        return DEFAULT_VALUE

    def _guess_challenge_scene(self, text: str) -> str:
        tags = [item for item in ["\u770b\u56fe", "\u770b\u516c\u5f0f", "\u5199\u4ee3\u7801", "\u505a\u9898", "\u542c\u8bfe", "\u5efa\u6a21", "\u753b\u56fe", "\u9700\u6c42\u5efa\u6a21"] if item in text]
        return "\u3001".join(tags) if tags else DEFAULT_VALUE

    def _build_summary(self, profile: Dict[str, str]) -> str:
        major = profile.get("major") or DEFAULT_VALUE
        course = profile.get("target_course") or DEFAULT_VALUE
        weak = profile.get("weak_points") or DEFAULT_VALUE
        style = profile.get("study_style") or DEFAULT_VALUE
        goal = profile.get("study_goal") or DEFAULT_VALUE
        time = profile.get("study_time_prefer") or DEFAULT_VALUE

        parts = []
        if major != DEFAULT_VALUE:
            parts.append(f"{major}\u65b9\u5411\u5b66\u751f")
        if course != DEFAULT_VALUE:
            parts.append(f"\u5f53\u524d\u805a\u7126{course}")
        if goal != DEFAULT_VALUE:
            parts.append(f"\u76ee\u6807\u662f{goal}")
        if weak != DEFAULT_VALUE:
            parts.append(f"\u4e3b\u8981\u77ed\u677f\u662f{weak}")
        if time != DEFAULT_VALUE:
            parts.append(f"\u503e\u5411\u4e8e{time}\u5b66\u4e60")
        if style != DEFAULT_VALUE:
            parts.append(f"\u504f\u597d{style}")

        return "\u3001".replace("\u3001", "\uff0c").join(parts) if parts else DEFAULT_VALUE
