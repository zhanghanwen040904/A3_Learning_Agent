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
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "preferred_resource",
    "knowledge_level",
    "study_style",
    "weak_points",
    "challenge_scene",
    "profile_summary",
]

CORE_PROFILE_DIMENSIONS = [
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "preferred_resource",
]

DEFAULT_VALUE = "待进一步观察"

FIELD_ALIASES = {
    "major": ["专业背景", "专业", "方向"],
    "target_course": ["目标课程", "课程", "章节"],
    "knowledge_base": ["知识基础", "基础情况", "基础水平", "知识水平"],
    "cognitive_style": ["认知风格", "学习方式", "学习风格", "学习偏好"],
    "error_prone_points": ["易错点", "易错点偏好", "知识短板", "薄弱点", "不会", "容易卡住"],
    "study_goal": ["学习目标", "目标", "希望达到"],
    "learning_history": ["学习历史", "学习经历", "历史表现", "做过", "学过"],
    "course_progress": ["课程进度", "学到哪里", "当前进度"],
    "study_time_prefer": ["时间节奏", "时间偏好", "学习时间", "效率最高"],
    "preferred_resource": ["资源偏好", "想优先看到", "喜欢的资源"],
    "knowledge_level": ["基础情况", "知识基础", "基础水平"],
    "study_style": ["学习方式", "学习风格", "学习偏好"],
    "weak_points": ["知识短板", "薄弱点", "不会", "容易卡住"],
    "challenge_scene": ["困难场景", "最常卡住", "跟不上"],
}

PROFILE_ANALYZE_PROMPT_TEMPLATE = """
你是学习画像分析师。请从学生自然语言对话中抽取结构化学习画像。
必须严格只返回 JSON，不要 markdown，不要解释。
JSON 字段必须完全一致：
{{"major":"","target_course":"","knowledge_base":"","cognitive_style":"","error_prone_points":"","study_goal":"","learning_history":"","course_progress":"","study_time_prefer":"","preferred_resource":"","knowledge_level":"","study_style":"","weak_points":"","challenge_scene":"","profile_summary":""}}

字段要求：
- major：学生专业或方向，作为画像上下文
- target_course：本次主要学习课程或章节，作为画像上下文
- knowledge_base：知识基础，描述已掌握内容、基础水平和先修知识状态
- cognitive_style：认知风格，描述偏好图解、案例、代码、视频、练习、抽象/实践等学习加工方式
- error_prone_points：易错点偏好，描述常错知识点、题型、概念混淆、文档/图表/代码等易错场景
- study_goal：学习目标，描述考试、作业、项目、实验、复习结果等目标
- learning_history：学习历史，描述已学章节、历史表现、作业实验、测试结果、已使用资源等
- course_progress：课程进度，描述当前学到的位置、近期任务和节点
- study_time_prefer：时间节奏，描述可投入时间、学习节奏和高效时段
- preferred_resource：资源偏好，描述更需要的资源类型，如图解、案例、分层练习、视频、代码实操等
- knowledge_level：兼容字段，等同于 knowledge_base
- study_style：兼容字段，等同于 cognitive_style
- weak_points：兼容字段，等同于 error_prone_points
- challenge_scene：兼容字段，描述困难场景，可从 error_prone_points 中归纳
- profile_summary：用 1 句话概括八维动态学习画像

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
  "profile": {{"major":"","target_course":"","knowledge_base":"","cognitive_style":"","error_prone_points":"","study_goal":"","learning_history":"","course_progress":"","study_time_prefer":"","preferred_resource":"","knowledge_level":"","study_style":"","weak_points":"","challenge_scene":"","profile_summary":""}},
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
- 八维画像中至少 6 个核心维度清晰后，is_complete 才可为 true；后续对话出现新学习历史、测试结果或资源偏好时，要随学随新地更新已有画像。

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
            output_schema='{"major":"","target_course":"","knowledge_base":"","cognitive_style":"","error_prone_points":"","study_goal":"","learning_history":"","course_progress":"","study_time_prefer":"","preferred_resource":"","knowledge_level":"","study_style":"","weak_points":"","challenge_scene":"","profile_summary":""}',
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
        return self._normalize_profile({field: str(data.get(field) or DEFAULT_VALUE) for field in PROFILE_FIELDS})

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
        if self._question_targets_filled_field(next_question, merged_profile, missing_fields):
            next_question = self._next_question_for_missing(missing_fields)
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
        self._sync_dimension_aliases(normalized)
        normalized["profile_summary"] = self._build_summary(normalized)
        return normalized

    def _sync_dimension_aliases(self, profile: Dict[str, str]) -> Dict[str, str]:
        alias_pairs = [
            ("knowledge_base", "knowledge_level"),
            ("cognitive_style", "study_style"),
            ("error_prone_points", "weak_points"),
        ]
        for primary, legacy in alias_pairs:
            primary_value = profile.get(primary) or DEFAULT_VALUE
            legacy_value = profile.get(legacy) or DEFAULT_VALUE
            if primary_value == DEFAULT_VALUE and legacy_value != DEFAULT_VALUE:
                profile[primary] = legacy_value
            if legacy_value == DEFAULT_VALUE and profile.get(primary) != DEFAULT_VALUE:
                profile[legacy] = profile[primary]
        if (profile.get("challenge_scene") or DEFAULT_VALUE) == DEFAULT_VALUE and profile.get("error_prone_points") != DEFAULT_VALUE:
            profile["challenge_scene"] = profile["error_prone_points"]
        return profile

    def _messages_to_dialogue(self, messages: List[Dict[str, str]]) -> str:
        lines = []
        for item in messages or []:
            role = "学生" if item.get("role") == "user" else "画像助手"
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role}：{content}")
        return "\n".join(lines)

    def _missing_fields(self, profile: Dict[str, str]) -> List[str]:
        return [field for field in CORE_PROFILE_DIMENSIONS if not profile.get(field) or profile.get(field) == DEFAULT_VALUE]

    def _confidence_by_profile(self, profile: Dict[str, str]) -> float:
        filled = len([field for field in CORE_PROFILE_DIMENSIONS if profile.get(field) and profile.get(field) != DEFAULT_VALUE])
        return round(filled / max(len(CORE_PROFILE_DIMENSIONS), 1), 2)

    def _question_targets_filled_field(self, question: str, profile: Dict[str, str], missing_fields: List[str]) -> bool:
        if not question:
            return False
        field_keywords = {
            "knowledge_base": ["知识基础", "基础如何", "哪些概念", "哪些内容已经掌握"],
            "cognitive_style": ["哪种方式", "学习方式", "认知风格", "图解", "案例"],
            "error_prone_points": ["容易出错", "混淆", "易错", "卡住"],
            "study_goal": ["学习结果", "学习目标", "希望", "考试", "作业"],
            "learning_history": ["之前学过", "学习历史", "作业", "实验", "测试"],
            "course_progress": ["学到哪里", "课程进度", "近期"],
            "study_time_prefer": ["每天", "多久", "时间段", "效率"],
            "preferred_resource": ["资源", "材料", "优先看到"],
        }
        for field, keywords in field_keywords.items():
            if field in missing_fields:
                continue
            value = profile.get(field) or DEFAULT_VALUE
            if value != DEFAULT_VALUE and any(keyword in question for keyword in keywords):
                return True
        return False

    def _next_question_for_missing(self, missing_fields: List[str]) -> str:
        questions = {
            "knowledge_base": "你目前对这门课的知识基础如何？哪些概念、方法或章节已经掌握，哪些还不稳定？",
            "cognitive_style": "你更容易通过哪种方式理解知识？例如图解、案例、代码实操、短视频、类比讲解或分层练习。",
            "error_prone_points": "你最容易出错或混淆的知识点、题型或学习场景是什么？可以举一个具体例子。",
            "study_goal": "你希望在什么时间内达到什么学习结果？例如考试、作业、实验、项目或复习目标。",
            "learning_history": "你之前学过哪些相关章节、做过哪些作业/实验/测试？效果如何？",
            "course_progress": "这门课你目前学到哪里了？近期有没有作业、实验、考试或项目节点？",
            "study_time_prefer": "你每天大概能投入多久学习？通常哪个时间段效率更高？",
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
        if result["knowledge_base"] == DEFAULT_VALUE:
            result["knowledge_base"] = self._guess_knowledge_level(text)
        if result["course_progress"] == DEFAULT_VALUE:
            result["course_progress"] = self._guess_course_progress(text)
        if result["cognitive_style"] == DEFAULT_VALUE:
            result["cognitive_style"] = self._guess_style(text)
        if result["preferred_resource"] == DEFAULT_VALUE:
            result["preferred_resource"] = self._guess_resource(text)
        if result["study_time_prefer"] == DEFAULT_VALUE:
            result["study_time_prefer"] = self._guess_time(text)
        if result["study_goal"] == DEFAULT_VALUE:
            result["study_goal"] = self._guess_goal(text)
        if result["error_prone_points"] == DEFAULT_VALUE:
            result["error_prone_points"] = self._guess_weak_point(text)
        if result["challenge_scene"] == DEFAULT_VALUE:
            result["challenge_scene"] = self._guess_challenge_scene(text)
        if result["learning_history"] == DEFAULT_VALUE:
            result["learning_history"] = self._guess_learning_history(text)
        self._sync_dimension_aliases(result)

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

    def _extract_learned_topics(self, text: str) -> str:
        patterns = [
            r"(?:之前|已经|已|曾经)?(?:学过|学习过|学习了|掌握了|了解了)([^。；;\n]{2,60})",
            r"(?:已掌握|已经掌握|比较熟悉)([^。；;\n]{2,60})",
        ]
        topics = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = self._clean_topic_phrase(match.group(1))
                if value and value not in topics:
                    topics.append(value)
        return "、".join(topics[:3]) if topics else DEFAULT_VALUE

    def _extract_unstable_topics(self, text: str) -> str:
        patterns = [
            r"但([^。；;\n]{2,60}?)(?:混淆|不稳定|不熟|不会|不太会|薄弱|卡住)",
            r"([^。；;\n]{2,60}?)(?:之间的关系|关系)(?:经常)?(?:容易)?(?:混淆|不清楚)",
        ]
        topics = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = self._clean_topic_phrase(match.group(1))
                if value and value not in topics:
                    topics.append(value)
        return "、".join(topics[:3]) if topics else DEFAULT_VALUE

    def _clean_topic_phrase(self, value: str) -> str:
        value = str(value or "").strip()
        value = re.split(r"但|但是|不过|然而", value)[0]
        value = re.sub(r"^(?:和|及|了|但|但是|目前|我|对|这门课的)", "", value)
        value = re.sub(r"(?:之间的关系|之间关系|的关系|之间)$", "", value)
        value = value.replace("，", "、").replace("和", "、")
        return value.strip(" 、，,。；;") or DEFAULT_VALUE

    def _guess_course_progress(self, text: str) -> str:
        learned = self._extract_learned_topics(text)
        if learned != DEFAULT_VALUE:
            return f"已学到{learned}"
        match = re.search(r"(?:当前|现在)?(?:学到|进度到)([^。；;\n]{2,40})", text)
        if match:
            value = self._clean_topic_phrase(match.group(1))
            return value if value != DEFAULT_VALUE else DEFAULT_VALUE
        return DEFAULT_VALUE

    def _guess_knowledge_level(self, text: str) -> str:
        if any(item in text for item in ["很多定义不太会", "很多定义不会", "定义不太会", "定义不会"]):
            return "定义理解薄弱"
        learned = self._extract_learned_topics(text)
        unstable = self._extract_unstable_topics(text)
        if learned != DEFAULT_VALUE and unstable != DEFAULT_VALUE:
            return f"已学习{learned}，但{unstable}仍不稳定"
        if learned != DEFAULT_VALUE:
            return f"已学习{learned}"
        candidates = ["零基础", "刚入门", "基础薄弱", "基础较弱", "基础一般", "基础不太好", "基础不好", "一般", "还可以", "有一定基础", "基础较好", "比较熟悉", "掌握较好"]
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
        score = re.search(r"(?:拿到|考到|达到)?\s*(\d{2,3})\s*分", text)
        if score:
            return f"拿到{score.group(1)}分"
        match = re.search(r"(?:希望|想要|目标是|目标)([^。；;\n]{2,60})", text)
        if match:
            value = match.group(1).strip()
            return value.strip("，,。；; ") or DEFAULT_VALUE
        if "期末复习" in text:
            return "期末复习"
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

    def _guess_learning_history(self, text: str) -> str:
        tags = []
        learned = self._extract_learned_topics(text)
        if learned != DEFAULT_VALUE:
            tags.append(f"之前学过{learned}")
        patterns = [
            r"(?:已经|已|之前|曾经)(?:学习|学过|完成|做过|练过)([^。；;\n]{2,40})",
            r"(?:作业|实验|测试|考试|项目)(?:[^。；;\n]{0,30})(?:做过|完成|得分|错题|反馈)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = match.group(0).strip()
                if value and value not in tags:
                    tags.append(value)
        return "、".join(tags[:3]) if tags else DEFAULT_VALUE

    def _build_summary(self, profile: Dict[str, str]) -> str:
        major = profile.get("major") or DEFAULT_VALUE
        course = profile.get("target_course") or DEFAULT_VALUE
        knowledge = profile.get("knowledge_base") or profile.get("knowledge_level") or DEFAULT_VALUE
        weak = profile.get("error_prone_points") or profile.get("weak_points") or DEFAULT_VALUE
        style = profile.get("cognitive_style") or profile.get("study_style") or DEFAULT_VALUE
        goal = profile.get("study_goal") or DEFAULT_VALUE
        history = profile.get("learning_history") or DEFAULT_VALUE
        time = profile.get("study_time_prefer") or DEFAULT_VALUE

        parts = []
        if major != DEFAULT_VALUE:
            parts.append(f"{major}方向学生")
        if course != DEFAULT_VALUE:
            parts.append(f"当前聚焦{course}")
        if knowledge != DEFAULT_VALUE:
            parts.append(f"知识基础为{knowledge}")
        if weak != DEFAULT_VALUE:
            parts.append(f"易错点集中在{weak}")
        if goal != DEFAULT_VALUE:
            parts.append(f"目标是{goal}")
        if history != DEFAULT_VALUE:
            parts.append(f"学习历史包含{history}")
        if time != DEFAULT_VALUE:
            parts.append(f"倾向于{time}学习")
        if style != DEFAULT_VALUE:
            parts.append(f"认知风格偏好{style}")

        return "，".join(parts) if parts else DEFAULT_VALUE
