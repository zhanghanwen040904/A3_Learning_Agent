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
        if result["study_style"] == DEFAULT_VALUE:
            result["study_style"] = self._guess_style(text)
        if result["preferred_resource"] == DEFAULT_VALUE:
            result["preferred_resource"] = self._guess_resource(text)
        if result["study_time_prefer"] == DEFAULT_VALUE:
            result["study_time_prefer"] = self._guess_time(text)
        if result["weak_points"] == DEFAULT_VALUE:
            result["weak_points"] = self._guess_weak_point(text)

        result["profile_summary"] = self._build_summary(result)
        return result

    def _extract_by_aliases(self, text: str, aliases: List[str]) -> str:
        for alias in aliases:
            match = re.search(rf"{re.escape(alias)}[：:\s]+(.+)", text)
            if match:
                value = match.group(1).strip().splitlines()[0].strip()
                return value or DEFAULT_VALUE
        return DEFAULT_VALUE

    def _guess_major(self, text: str) -> str:
        candidates = ["软件工程", "人工智能", "计算机科学与技术", "计算机", "数据科学", "网络工程", "自动化"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_course(self, text: str) -> str:
        candidates = ["软件工程", "需求分析", "可行性研究", "总体设计", "详细设计", "软件测试", "软件维护", "软件生命周期", "结构化设计"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_style(self, text: str) -> str:
        tags = [item for item in ["图解", "案例", "分层练习", "视频", "代码", "讲解"] if item in text]
        return "、".join(tags) if tags else DEFAULT_VALUE

    def _guess_resource(self, text: str) -> str:
        tags = [item for item in ["讲解文档", "思维导图", "练习题", "代码案例", "视频", "拓展阅读", "图解"] if item in text]
        return " + ".join(tags) if tags else DEFAULT_VALUE

    def _guess_time(self, text: str) -> str:
        parts = [item for item in ["晚上", "白天", "周末", "碎片时间", "60分钟", "1小时", "两小时"] if item in text]
        return "，".join(parts) if parts else DEFAULT_VALUE

    def _guess_weak_point(self, text: str) -> str:
        candidates = ["需求分析", "可行性研究", "总体设计", "详细设计", "软件测试", "软件维护", "软件生命周期", "数据流图", "模块设计", "编码实现"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _build_summary(self, profile: Dict[str, str]) -> str:
        major = profile.get("major") or DEFAULT_VALUE
        course = profile.get("target_course") or DEFAULT_VALUE
        weak = profile.get("weak_points") or DEFAULT_VALUE
        style = profile.get("study_style") or DEFAULT_VALUE

        parts = []
        if major != DEFAULT_VALUE:
            parts.append(f"{major}方向学生")
        if course != DEFAULT_VALUE:
            parts.append(f"当前聚焦{course}")
        if weak != DEFAULT_VALUE:
            parts.append(f"主要短板是{weak}")
        if style != DEFAULT_VALUE:
            parts.append(f"偏好{style}式学习")

        return "，".join(parts) if parts else DEFAULT_VALUE
