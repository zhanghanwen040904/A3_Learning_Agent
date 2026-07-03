import json
import re
from typing import Any, Dict, List, Optional

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.llm_adapter import PlatformLLM
from ai.langchain_parsers import parse_json_with_fallback
from config import config
from .base_agent import AgentSpec

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
    "error_prone_points": ["易错点", "知识短板", "薄弱点", "不会", "容易卡住"],
    "study_goal": ["学习目标", "目标", "希望达到"],
    "learning_history": ["学习历史", "学习经历", "历史表现", "做过", "学过"],
    "course_progress": ["课程进度", "学到哪里", "当前进度"],
    "study_time_prefer": ["时间节奏", "时间偏好", "学习时间", "效率最高"],
    "preferred_resource": ["资源偏好", "优先看", "喜欢的资源"],
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

如信息不足，请合理填写“{default_value}”。

学生对话：
{dialogue_text}
""".strip()

PROFILE_CHAT_PROMPT_TEMPLATE = """
你是高校课程学习助手。系统主功能是对话式答疑，学习画像只在后台静默更新。

请根据【完整多轮对话】和【当前画像草稿】完成两件事：
1. 正常回答学生当前这条消息，优先解决用户眼前的问题；
2. 从整段对话中静默抽取或更新学习画像。

重要要求：
- 每一次对话都默认用于补充画像，但不要显式提问画像；
- 不要主动追问“还缺什么信息”“你的基础如何”“你偏好什么资源”之类画像问题；
- assistant_reply 必须是自然、直接、像主流智能体那样的帮助性回复；
- assistant_reply 必须真正回应学生当前这条消息，禁止只说“我已记录”“我会更新画像”“请继续提问”这类空泛套话，除非用户本身只是在做信息补充且没有提出任何具体问题；
- next_question 固定返回空字符串；
- reply_type 固定返回 answer_only；
- 画像要综合上下文，不要只复制最后一句。

必须严格只返回 JSON，不要 markdown，不要解释。JSON 字段必须完全一致：
{{
  "profile": {{"major":"","target_course":"","knowledge_base":"","cognitive_style":"","error_prone_points":"","study_goal":"","learning_history":"","course_progress":"","study_time_prefer":"","preferred_resource":"","knowledge_level":"","study_style":"","weak_points":"","challenge_scene":"","profile_summary":""}},
  "assistant_reply": "",
  "reply_type": "answer_only",
  "missing_fields": [],
  "next_question": "",
  "confidence": 0.0,
  "is_complete": false,
  "reasoning_note": ""
}}

当前画像草稿：
{base_profile}

完整多轮对话：
{messages}
""".strip()

PROFILE_ANALYZE_PROMPT = LangChainPromptTemplate.from_template(PROFILE_ANALYZE_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None
PROFILE_CHAT_PROMPT = LangChainPromptTemplate.from_template(PROFILE_CHAT_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class ProfileAgent:
    """从学生对话中抽取结构化学习画像。"""

    def __init__(self):
        self.role = "学习画像分析师"
        self.goal = "从学生自然语言对话中抽取学习画像，并在问答场景下静默更新画像。"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["langchain_prompt", "platform_llm"],
            input_schema="学生自然语言对话文本",
            output_schema='{"major":"","target_course":"","knowledge_base":"","cognitive_style":"","error_prone_points":"","study_goal":"","learning_history":"","course_progress":"","study_time_prefer":"","preferred_resource":"","knowledge_level":"","study_style":"","weak_points":"","challenge_scene":"","profile_summary":""}',
        )
        self.analyze_chain = (PROFILE_ANALYZE_PROMPT | PlatformLLM() | LangChainStrOutputParser()) if PROFILE_ANALYZE_PROMPT is not None and LangChainStrOutputParser is not None else None
        self.chat_chain = (PROFILE_CHAT_PROMPT | PlatformLLM() | LangChainStrOutputParser()) if PROFILE_CHAT_PROMPT is not None and LangChainStrOutputParser is not None else None

    def analyze(self, dialogue_text: str) -> Dict[str, str]:
        parsed = self._extract_from_dialogue(dialogue_text)
        if config.MOCK_AI:
            return parsed

        variables = {"default_value": DEFAULT_VALUE, "dialogue_text": dialogue_text}
        if self.analyze_chain is not None:
            raw = self.analyze_chain.invoke(variables)
        else:
            raw = PlatformLLM().invoke(PROFILE_ANALYZE_PROMPT_TEMPLATE.format(**variables))
        model_result = self._parse_profile(raw)
        return self._merge_profile(model_result, parsed)

    def _parse_profile(self, raw: str) -> Dict[str, str]:
        data = parse_json_with_fallback(raw)
        return self._normalize_profile({field: str(data.get(field) or DEFAULT_VALUE) for field in PROFILE_FIELDS})

    def chat_extract(self, messages: List[Dict[str, str]], current_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current_profile = current_profile or {}
        dialogue_text = self._messages_to_dialogue(messages)
        parsed_from_messages = self._extract_from_dialogue(dialogue_text)
        base_profile = self._normalize_profile({**current_profile, **{k: v for k, v in parsed_from_messages.items() if v != DEFAULT_VALUE}})
        latest_user_message = self._latest_user_message(messages)

        if config.MOCK_AI:
            return self._build_chat_result(base_profile, source="mock_fallback", latest_user_message=latest_user_message)

        variables = {
            "base_profile": json.dumps(base_profile, ensure_ascii=False),
            "messages": json.dumps(messages, ensure_ascii=False),
        }
        if self.chat_chain is not None:
            raw = self.chat_chain.invoke(variables)
        else:
            raw = PlatformLLM().invoke(PROFILE_CHAT_PROMPT_TEMPLATE.format(**variables))

        data = parse_json_with_fallback(raw)
        model_profile = self._normalize_profile(data.get("profile") or {})
        merged_profile = self._merge_profile(model_profile, base_profile)
        missing_fields = self._missing_fields(merged_profile)

        assistant_reply = str(data.get("assistant_reply") or "").strip()
        if not assistant_reply:
            assistant_reply = "当前大模型未返回有效答复，请重试一次；我会继续在后台保留并更新你的学习画像。"

        is_complete = bool(data.get("is_complete")) and len(missing_fields) <= 4
        confidence = data.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = self._confidence_by_profile(merged_profile)

        return {
            "profile": merged_profile,
            "missing_fields": missing_fields,
            "assistant_reply": assistant_reply,
            "reply_type": "answer_only",
            "next_question": "",
            "confidence": max(0.0, min(1.0, confidence)),
            "is_complete": is_complete or len(missing_fields) <= 4,
            "reasoning_note": str(data.get("reasoning_note") or "已基于多轮上下文完成问题回答与后台画像更新。"),
            "model_enabled": True,
            "source": "llm_chat",
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
            if legacy_value == DEFAULT_VALUE and primary_value != DEFAULT_VALUE:
                profile[legacy] = primary_value
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

    def _latest_user_message(self, messages: List[Dict[str, str]]) -> str:
        for item in reversed(messages or []):
            if item.get("role") == "user":
                return str(item.get("content") or "").strip()
        return ""

    def _missing_fields(self, profile: Dict[str, str]) -> List[str]:
        return [field for field in CORE_PROFILE_DIMENSIONS if not profile.get(field) or profile.get(field) == DEFAULT_VALUE]

    def _confidence_by_profile(self, profile: Dict[str, str]) -> float:
        filled = len([field for field in CORE_PROFILE_DIMENSIONS if profile.get(field) and profile.get(field) != DEFAULT_VALUE])
        return round(filled / max(len(CORE_PROFILE_DIMENSIONS), 1), 2)

    def _build_chat_result(self, profile: Dict[str, str], source: str, latest_user_message: str = "") -> Dict[str, Any]:
        missing_fields = self._missing_fields(profile)
        return {
            "profile": profile,
            "missing_fields": missing_fields,
            "assistant_reply": self._build_mock_reply(latest_user_message, profile),
            "reply_type": "answer_only",
            "next_question": "",
            "confidence": self._confidence_by_profile(profile),
            "is_complete": len(missing_fields) <= 4,
            "reasoning_note": "当前为 MOCK_AI 演示模式，使用本地规则进行问题回答和画像提取。",
            "model_enabled": False,
            "source": source,
        }

    def _build_mock_reply(self, latest_user_message: str, profile: Dict[str, str]) -> str:
        text = str(latest_user_message or "").strip()
        if not text:
            return "你好，你可以直接问我课程、章节、知识点、题目或学习方法，我会在后台同步更新学习画像。"

        course = profile.get("target_course") or self._guess_course(text)

        if any(keyword in text for keyword in ["哪些章节", "有哪些章节", "章节有哪些", "目录", "知识点有哪些"]):
            if "软件工程" in course:
                return "如果你现在学的是软件工程，常见章节一般包括：软件工程概述、软件生命周期、可行性研究、需求分析、总体设计、详细设计、编码实现、软件测试、维护与项目管理。你告诉我想先看哪一章，我就按那一章继续帮你。"
            return "你先告诉我具体是哪门课程，我就能按这门课给你列章节；如果暂时只想快速开始，也可以直接告诉我你想先学哪个知识点。"

        if any(keyword in text for keyword in ["回答我的问题", "先回答", "直接回答", "先告诉我"]):
            return "收到，我会优先直接回答你的问题，画像只在后台静默更新，不再打断你的主问题。你继续发具体问题就行。"

        if "画像" in text and any(keyword in text for keyword in ["分析", "总结", "看看", "生成"]):
            return "可以，我会继续依据我们所有对话静默更新画像；如果你需要，我也可以单独给你一版当前画像总结。"

        return "我已经收到你的信息，并会在后台同步更新学习画像。你可以继续直接问课程、章节、题目或学习上的具体问题，我优先回答问题本身。"

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
            "A": "图文讲解",
            "Ａ": "图文讲解",
            "B": "代码示例",
            "Ｂ": "代码示例",
            "C": "思维导图",
            "Ｃ": "思维导图",
            "D": "其他方式",
            "Ｄ": "其他方式",
        }
        for key, value in option_map.items():
            choose_pattern = rf"(?:选择|选|我选|我选择){re.escape(key)}(?:$|[。，,.;\s])"
            tail_pattern = rf"(?:^|[\n\r我：:]){re.escape(key)}$"
            if re.search(choose_pattern, compact) or re.search(tail_pattern, compact):
                return value
        if re.fullmatch(r"[A-DＡ-Ｄ]", compact):
            return option_map.get(compact, normalized)
        return normalized

    def _guess_major(self, text: str) -> str:
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z0-9]+(?:与技术|科学|工程|专业))专业学生",
            r"我是([\u4e00-\u9fa5A-Za-z0-9]+)专业",
            r"专业[是为:：\s]+([\u4e00-\u9fa5A-Za-z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = re.sub(r"学生$", "", match.group(1).strip())
                return value or DEFAULT_VALUE

        candidates = ["计算机科学与技术", "计算机科学", "人工智能", "计算机", "数据科学", "网络工程", "自动化", "软件工程"]
        for item in candidates:
            if item in text:
                if item == "软件工程" and re.search(r"软件工程(?:课|课程|章节)", text):
                    continue
                return item
        return DEFAULT_VALUE

    def _guess_course(self, text: str) -> str:
        course_patterns = [
            r"学习([\u4e00-\u9fa5A-Za-z0-9]+?)课程",
            r"针对([\u4e00-\u9fa5A-Za-z0-9]+?)课",
            r"课程[是为:：\s]+([\u4e00-\u9fa5A-Za-z0-9]+)",
        ]
        for pattern in course_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if "软件工程" in text:
            return "软件工程"
        candidates = ["需求分析", "可行性研究", "总体设计", "详细设计", "软件测试", "软件维护", "软件生命周期", "结构化设计"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _extract_learned_topics(self, text: str) -> str:
        patterns = [
            r"(?:之前|已经|曾经)?(?:学过|学习过|学习了|掌握了|了解了)([^。；;\n]{2,60})",
            r"(?:已掌握|已经掌握|比较熟悉)([^。；;\n]{2,60})",
        ]
        topics = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = self._clean_topic_phrase(match.group(1))
                if value != DEFAULT_VALUE and value not in topics:
                    topics.append(value)
        return "、".join(topics[:3]) if topics else DEFAULT_VALUE

    def _extract_unstable_topics(self, text: str) -> str:
        patterns = [
            r"([^。；;\n]{2,60}?)(?:混淆|不稳定|不熟|不会|不太会|薄弱|卡住)",
            r"([^。；;\n]{2,60}?)(?:之间的关系)(?:经常)?(?:容易)?(?:混淆|不清楚)",
        ]
        topics = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = self._clean_topic_phrase(match.group(1))
                if value != DEFAULT_VALUE and value not in topics:
                    topics.append(value)
        return "、".join(topics[:3]) if topics else DEFAULT_VALUE

    def _clean_topic_phrase(self, value: str) -> str:
        value = str(value or "").strip()
        value = re.split(r"但是|不过|然后", value)[0]
        value = re.sub(r"^(?:和|以及|还有|目前|我对|这门课的)", "", value)
        value = re.sub(r"(?:之间的关系|的关系)$", "", value)
        value = value.strip(" 、，,。；;")
        return value or DEFAULT_VALUE

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
            return f"已学过{learned}，但{unstable}仍不稳定"
        if learned != DEFAULT_VALUE:
            return f"已学过{learned}"
        candidates = ["零基础", "刚入门", "基础薄弱", "基础较弱", "基础一般", "还可以", "有一定基础", "基础较好", "比较熟悉", "掌握较好"]
        for item in candidates:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_style(self, text: str) -> str:
        normalized = self._normalize_choice_text(text)
        explicit = ["图文讲解", "代码示例", "思维导图", "图解", "案例", "分层练习", "视频", "代码实操", "讲解"]
        tags = [item for item in explicit if item in normalized]
        if "图文讲解" in tags:
            tags = [item for item in tags if item not in {"图解", "讲解"}]
        return "、".join(tags[:3]) if tags else DEFAULT_VALUE

    def _guess_resource(self, text: str) -> str:
        normalized = self._normalize_choice_text(text)
        explicit = ["图文讲解", "代码示例", "思维导图", "讲解文档", "练习题", "代码案例", "视频", "拓展阅读", "图解"]
        tags = [item for item in explicit if item in normalized]
        if "图文讲解" in tags:
            tags = [item for item in tags if item != "图解"]
        return "、".join(tags[:3]) if tags else DEFAULT_VALUE

    def _guess_time(self, text: str) -> str:
        parts = []
        if re.search(r"晚上\s*12\s*点|12\s*点", text):
            parts.append("晚上12点")
        parts.extend(item for item in ["晚上", "白天", "周末", "碎片时间", "60分钟", "1小时", "两小时"] if item in text and item not in parts)
        return "、".join(parts) if parts else DEFAULT_VALUE

    def _guess_goal(self, text: str) -> str:
        score = re.search(r"(?:拿到|考到|达到)?\s*(\d{2,3})\s*分", text)
        if score:
            return f"拿到{score.group(1)}分"
        match = re.search(r"(?:希望|想要|目标是|目标)([^。；;\n]{2,60})", text)
        if match:
            value = match.group(1).strip(" ：:，,。；; ")
            return value or DEFAULT_VALUE
        if "期末复习" in text:
            return "期末复习"
        return DEFAULT_VALUE

    def _guess_weak_point(self, text: str) -> str:
        candidates = ["瀑布模型", "需求分析", "可行性研究", "总体设计", "详细设计", "软件测试", "软件维护", "软件生命周期", "数据流图", "模块设计", "编码实现", "数据字典"]
        hits = [item for item in candidates if item in text]
        if hits:
            return "、".join(hits[:4])
        if any(item in text for item in ["定义不清", "定义不会", "概念混淆"]):
            return "定义理解困难"
        return DEFAULT_VALUE

    def _guess_challenge_scene(self, text: str) -> str:
        tags = [item for item in ["看图", "看公式", "写代码", "做题", "听课", "建模", "画图", "需求建模"] if item in text]
        return "、".join(tags) if tags else DEFAULT_VALUE

    def _guess_learning_history(self, text: str) -> str:
        tags = []
        learned = self._extract_learned_topics(text)
        if learned != DEFAULT_VALUE:
            tags.append(f"之前学过{learned}")
        patterns = [
            r"(?:已经|之前|曾经)(?:学习|学过|完成|做过|练过)([^。；;\n]{2,40})",
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
            parts.append(f"知识基础：{knowledge}")
        if weak != DEFAULT_VALUE:
            parts.append(f"易错点：{weak}")
        if goal != DEFAULT_VALUE:
            parts.append(f"目标：{goal}")
        if history != DEFAULT_VALUE:
            parts.append(f"学习历史包含{history}")
        if time != DEFAULT_VALUE:
            parts.append(f"偏向在{time}学习")
        if style != DEFAULT_VALUE:
            parts.append(f"认知风格偏好{style}")

        return "；".join(parts) if parts else DEFAULT_VALUE
