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

DEFAULT_VALUE = "待进一步观察"

CORE_PROFILE_DIMENSIONS = [
    "current_topic",
    "mastery_level",
    "current_difficulty",
    "task_goal",
    "support_preference",
    "engagement_level",
]

PROFILE_FIELDS = [
    "major",
    "target_course",
    "current_topic",
    "mastery_level",
    "current_difficulty",
    "task_goal",
    "support_preference",
    "engagement_level",
    "learning_background",
    "recent_progress",
    "schedule_pattern",
    "preferred_resource",
    "weak_knowledge_points",
    "recommended_next_step",
    "portrait_confidence",
    "profile_summary",
    # legacy compatibility fields
    "knowledge_base",
    "cognitive_style",
    "error_prone_points",
    "study_goal",
    "learning_history",
    "course_progress",
    "study_time_prefer",
    "knowledge_level",
    "study_style",
    "weak_points",
    "challenge_scene",
]

FIELD_LABELS = {
    "major": "专业背景",
    "target_course": "聚焦课程",
    "current_topic": "当前学习主题",
    "mastery_level": "掌握程度",
    "current_difficulty": "当前困难点",
    "task_goal": "当前任务目标",
    "support_preference": "适配支持方式",
    "engagement_level": "学习投入状态",
    "learning_background": "学习背景",
    "recent_progress": "最近进展",
    "schedule_pattern": "学习节奏",
    "preferred_resource": "偏好资源",
    "weak_knowledge_points": "薄弱知识点",
    "recommended_next_step": "下一步建议",
    "portrait_confidence": "画像置信度",
}

ANALYZE_PROMPT_TEMPLATE = """
你是一名高校学习画像分析助手。你的任务不是追问用户，而是根据已有对话，静默抽取一个“适合学习支持系统使用”的学生画像。

请严格只输出 JSON，不要输出 markdown，不要解释。
字段必须完整，未知时填“{default_value}”。

字段说明：
- current_topic：当前正在讨论或学习的具体主题/章节/知识点
- mastery_level：当前掌握状态，只能用简洁短语，如“入门起步 / 基础未稳 / 有一定基础 / 掌握较好”
- current_difficulty：当前最明显的困难、卡点或不清楚的地方
- task_goal：当前这轮学习最直接的目标
- support_preference：当前更适合的支持方式，如“通俗讲解 / 图解梳理 / 例题带练 / 代码示例 / 分步骤说明”
- engagement_level：当前投入状态，如“刚开始接触 / 持续学习中 / 复习巩固中 / 冲刺提升中”
- learning_background：用户体现出的既有背景或起点
- recent_progress：最近学到哪里、正在推进什么
- schedule_pattern：若提到了时间习惯则提取，否则填默认值
- preferred_resource：若提到了资源偏好则提取，否则填默认值
- weak_knowledge_points：更偏知识点层面的薄弱项
- recommended_next_step：一句简短、可执行的下一步建议
- portrait_confidence：只能填“低 / 中 / 高”
- profile_summary：一句综合摘要，不超过80字

输出字段：
{{
  "major": "",
  "target_course": "",
  "current_topic": "",
  "mastery_level": "",
  "current_difficulty": "",
  "task_goal": "",
  "support_preference": "",
  "engagement_level": "",
  "learning_background": "",
  "recent_progress": "",
  "schedule_pattern": "",
  "preferred_resource": "",
  "weak_knowledge_points": "",
  "recommended_next_step": "",
  "portrait_confidence": "",
  "profile_summary": ""
}}

对话内容：
{dialogue_text}
""".strip()

CHAT_EXTRACT_PROMPT_TEMPLATE = """
你是一名高校课程学习助手。当前主任务是：
1. 回答学生这次真正提出的问题；
2. 同时静默更新学生画像，但不要显式追问画像。

要求：
- assistant_reply 必须直接解决学生当前问题，不能只说“我已记录”“请继续补充”
- 不主动追问画像缺失项
- 画像提取要结合整段对话，而不是只看最后一句
- 严格只输出 JSON
- 未知字段填“{default_value}”

返回格式：
{{
  "profile": {{
    "major": "",
    "target_course": "",
    "current_topic": "",
    "mastery_level": "",
    "current_difficulty": "",
    "task_goal": "",
    "support_preference": "",
    "engagement_level": "",
    "learning_background": "",
    "recent_progress": "",
    "schedule_pattern": "",
    "preferred_resource": "",
    "weak_knowledge_points": "",
    "recommended_next_step": "",
    "portrait_confidence": "",
    "profile_summary": ""
  }},
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

ANALYZE_PROMPT = LangChainPromptTemplate.from_template(ANALYZE_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None
CHAT_EXTRACT_PROMPT = LangChainPromptTemplate.from_template(CHAT_EXTRACT_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class ProfileAgent:
    def __init__(self):
        self.role = "学生画像分析助手"
        self.goal = "从自然对话中沉淀可服务学习支持系统的动态学习画像"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["platform_llm"],
            input_schema="多轮自然语言对话",
            output_schema=json.dumps({field: "" for field in PROFILE_FIELDS if field not in {
                "knowledge_base",
                "cognitive_style",
                "error_prone_points",
                "study_goal",
                "learning_history",
                "course_progress",
                "study_time_prefer",
                "knowledge_level",
                "study_style",
                "weak_points",
                "challenge_scene",
            }}, ensure_ascii=False),
        )
        self.analyze_chain = (
            ANALYZE_PROMPT | PlatformLLM() | LangChainStrOutputParser()
            if ANALYZE_PROMPT is not None and LangChainStrOutputParser is not None
            else None
        )
        self.chat_chain = (
            CHAT_EXTRACT_PROMPT | PlatformLLM() | LangChainStrOutputParser()
            if CHAT_EXTRACT_PROMPT is not None and LangChainStrOutputParser is not None
            else None
        )

    def analyze(self, dialogue_text: str) -> Dict[str, str]:
        heuristic_profile = self._extract_from_dialogue(dialogue_text)
        if config.MOCK_AI:
            return heuristic_profile

        variables = {"default_value": DEFAULT_VALUE, "dialogue_text": dialogue_text}
        raw = self.analyze_chain.invoke(variables) if self.analyze_chain is not None else PlatformLLM().invoke(
            ANALYZE_PROMPT_TEMPLATE.format(**variables)
        )
        model_profile = self._parse_profile(raw)
        return self._merge_profile(heuristic_profile, model_profile)

    def _parse_profile(self, raw: str) -> Dict[str, str]:
        return self._normalize_profile(parse_json_with_fallback(raw))

    def chat_extract(self, messages: List[Dict[str, str]], current_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        current_profile = current_profile or {}
        dialogue_text = self._messages_to_dialogue(messages)
        heuristic_profile = self._extract_from_dialogue(dialogue_text)
        base_profile = self._merge_profile(self._normalize_profile(current_profile), heuristic_profile)

        if config.MOCK_AI:
            return self._build_chat_result(base_profile, latest_user_message=self._latest_user_message(messages), source="mock")

        variables = {
            "default_value": DEFAULT_VALUE,
            "base_profile": json.dumps(base_profile, ensure_ascii=False),
            "messages": json.dumps(messages, ensure_ascii=False),
        }
        raw = self.chat_chain.invoke(variables) if self.chat_chain is not None else PlatformLLM().invoke(
            CHAT_EXTRACT_PROMPT_TEMPLATE.format(**variables)
        )
        data = parse_json_with_fallback(raw)
        model_profile = self._normalize_profile(data.get("profile") or {})
        merged_profile = self._merge_profile(base_profile, model_profile)
        confidence = self._safe_float(data.get("confidence"), self._confidence_by_profile(merged_profile))
        assistant_reply = str(data.get("assistant_reply") or "").strip()
        if not assistant_reply:
            assistant_reply = self._build_mock_reply(self._latest_user_message(messages), merged_profile)

        missing_fields = self._missing_fields(merged_profile)
        return {
            "profile": merged_profile,
            "missing_fields": missing_fields,
            "assistant_reply": assistant_reply,
            "reply_type": "answer_only",
            "next_question": "",
            "confidence": max(0.0, min(1.0, confidence)),
            "is_complete": len(missing_fields) <= 1,
            "reasoning_note": str(data.get("reasoning_note") or "已基于整段对话静默更新学生画像。"),
            "model_enabled": True,
            "source": "llm_chat_extract",
        }

    def _safe_float(self, value: Any, fallback: float) -> float:
        try:
            return float(value)
        except Exception:
            return fallback

    def _normalize_profile(self, profile: Dict[str, Any]) -> Dict[str, str]:
        raw = {field: self._clean_value(profile.get(field)) for field in PROFILE_FIELDS}

        raw["major"] = raw["major"] if raw["major"] != DEFAULT_VALUE else self._clean_value(profile.get("major_name"))

        # old -> new
        if raw["mastery_level"] == DEFAULT_VALUE:
            raw["mastery_level"] = self._first_meaningful(raw["knowledge_base"], raw["knowledge_level"])
        if raw["support_preference"] == DEFAULT_VALUE:
            raw["support_preference"] = self._first_meaningful(raw["cognitive_style"], raw["study_style"])
        if raw["current_difficulty"] == DEFAULT_VALUE:
            raw["current_difficulty"] = self._first_meaningful(raw["error_prone_points"], raw["weak_points"], raw["challenge_scene"])
        if raw["task_goal"] == DEFAULT_VALUE:
            raw["task_goal"] = raw["study_goal"]
        if raw["learning_background"] == DEFAULT_VALUE:
            raw["learning_background"] = raw["learning_history"]
        if raw["recent_progress"] == DEFAULT_VALUE:
            raw["recent_progress"] = self._first_meaningful(raw["course_progress"], raw["current_topic"])
        if raw["schedule_pattern"] == DEFAULT_VALUE:
            raw["schedule_pattern"] = raw["study_time_prefer"]
        if raw["weak_knowledge_points"] == DEFAULT_VALUE:
            raw["weak_knowledge_points"] = self._first_meaningful(raw["weak_points"], raw["error_prone_points"])

        # new -> old
        raw["knowledge_base"] = self._first_meaningful(raw["knowledge_base"], raw["mastery_level"])
        raw["knowledge_level"] = self._first_meaningful(raw["knowledge_level"], raw["mastery_level"])
        raw["cognitive_style"] = self._first_meaningful(raw["cognitive_style"], raw["support_preference"])
        raw["study_style"] = self._first_meaningful(raw["study_style"], raw["support_preference"])
        raw["error_prone_points"] = self._first_meaningful(raw["error_prone_points"], raw["current_difficulty"])
        raw["weak_points"] = self._first_meaningful(raw["weak_points"], raw["weak_knowledge_points"], raw["current_difficulty"])
        raw["challenge_scene"] = self._first_meaningful(raw["challenge_scene"], raw["current_difficulty"])
        raw["study_goal"] = self._first_meaningful(raw["study_goal"], raw["task_goal"])
        raw["learning_history"] = self._first_meaningful(raw["learning_history"], raw["learning_background"])
        raw["course_progress"] = self._first_meaningful(raw["course_progress"], raw["recent_progress"], raw["current_topic"])
        raw["study_time_prefer"] = self._first_meaningful(raw["study_time_prefer"], raw["schedule_pattern"])

        if raw["recommended_next_step"] == DEFAULT_VALUE:
            raw["recommended_next_step"] = self._derive_next_step(raw)
        if raw["portrait_confidence"] == DEFAULT_VALUE:
            raw["portrait_confidence"] = self._confidence_label(raw)
        raw["profile_summary"] = self._build_summary(raw)
        return raw

    def _merge_profile(self, base: Dict[str, str], incoming: Dict[str, str]) -> Dict[str, str]:
        merged = {}
        for field in PROFILE_FIELDS:
            base_value = self._clean_value(base.get(field))
            incoming_value = self._clean_value(incoming.get(field))
            merged[field] = incoming_value if incoming_value != DEFAULT_VALUE else base_value
        return self._normalize_profile(merged)

    def _messages_to_dialogue(self, messages: List[Dict[str, str]]) -> str:
        lines = []
        for item in messages or []:
            role = "学生" if item.get("role") == "user" else "学习助手"
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
        return [field for field in CORE_PROFILE_DIMENSIONS if self._clean_value(profile.get(field)) == DEFAULT_VALUE]

    def _confidence_by_profile(self, profile: Dict[str, str]) -> float:
        filled = len([field for field in CORE_PROFILE_DIMENSIONS if self._clean_value(profile.get(field)) != DEFAULT_VALUE])
        return round(filled / max(len(CORE_PROFILE_DIMENSIONS), 1), 2)

    def _build_chat_result(self, profile: Dict[str, str], latest_user_message: str = "", source: str = "fallback") -> Dict[str, Any]:
        missing_fields = self._missing_fields(profile)
        return {
            "profile": profile,
            "missing_fields": missing_fields,
            "assistant_reply": self._build_mock_reply(latest_user_message, profile),
            "reply_type": "answer_only",
            "next_question": "",
            "confidence": self._confidence_by_profile(profile),
            "is_complete": len(missing_fields) <= 1,
            "reasoning_note": "当前使用本地兜底画像提取逻辑。",
            "model_enabled": False,
            "source": source,
        }

    def _build_mock_reply(self, latest_user_message: str, profile: Dict[str, str]) -> str:
        text = str(latest_user_message or "").strip()
        if not text:
            return "你可以直接问课程、知识点、题目、学习方法或复习安排，我会优先帮你解决问题，并在后台自动更新画像。"
        if any(keyword in text for keyword in ["分为几章", "几个章节", "目录", "有哪些章节"]):
            course = profile.get("target_course")
            if course and course != DEFAULT_VALUE:
                return f"{course}一般会先讲课程概览，再进入需求、设计、实现、测试、维护等模块。你如果愿意，我可以继续按章节给你顺下来。"
            return "这门课通常会先讲整体框架，再展开到具体章节。你告诉我是哪门课，我可以直接按章节给你梳理。"
        if any(keyword in text for keyword in ["怎么学", "如何学", "学习路线"]):
            return "可以，我们可以按“先搭框架、再攻薄弱点、最后做题或案例巩固”的顺序来学。我也可以直接给你拆成一版短期学习路线。"
        return "收到，我会优先回答你当前的问题，同时把这轮对话静默计入画像里。你可以继续直接问具体内容。"

    def _extract_from_dialogue(self, dialogue_text: str) -> Dict[str, str]:
        text = str(dialogue_text or "").strip()
        latest_user = self._extract_latest_user_text(text)
        source = latest_user or text
        result = {field: DEFAULT_VALUE for field in PROFILE_FIELDS}

        if not source:
            return self._normalize_profile(result)

        result["major"] = self._guess_major(text)
        result["target_course"] = self._guess_course(text)
        result["current_topic"] = self._guess_current_topic(source, result["target_course"])
        result["mastery_level"] = self._guess_mastery_level(source)
        result["current_difficulty"] = self._guess_current_difficulty(source)
        result["task_goal"] = self._guess_task_goal(source, result["target_course"])
        result["support_preference"] = self._guess_support_preference(text)
        result["engagement_level"] = self._guess_engagement_level(text)
        result["learning_background"] = self._guess_learning_background(text, result["mastery_level"])
        result["recent_progress"] = self._guess_recent_progress(text, result["current_topic"])
        result["schedule_pattern"] = self._guess_schedule_pattern(text)
        result["preferred_resource"] = self._guess_resource_preference(text)
        result["weak_knowledge_points"] = self._guess_weak_knowledge_points(text, result["current_difficulty"])
        result["recommended_next_step"] = self._derive_next_step(result)
        result["portrait_confidence"] = self._confidence_label(result)
        return self._normalize_profile(result)

    def _extract_latest_user_text(self, text: str) -> str:
        lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("学生："):
                return line.replace("学生：", "", 1).strip()
        return lines[-1] if lines else ""

    def _guess_major(self, text: str) -> str:
        patterns = ["软件工程", "计算机科学与技术", "人工智能", "数据科学", "网络工程", "信息安全"]
        for item in patterns:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_course(self, text: str) -> str:
        patterns = ["软件工程", "人工智能导论", "数据结构", "操作系统", "计算机组成原理", "数据库原理"]
        for item in patterns:
            if item in text:
                return item
        return DEFAULT_VALUE

    def _guess_current_topic(self, text: str, course: str) -> str:
        explicit_patterns = [
            r"[“\"']([^”\"']{2,24})[”\"']这个部分",
            r"关于([^，。！？\n]{2,24})",
            r"学习([^，。！？\n]{2,24})",
            r"复习([^，。！？\n]{2,24})",
            r"解释知识点[“\"']?([^”\"'\n]{2,24})",
            r"([^，。！？\n]{2,24})怎么学",
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).strip()
                if len(candidate) >= 2:
                    return candidate
        for token in ["Scrum", "Sprint", "需求分析", "总体设计", "详细设计", "软件测试", "软件生命周期", "可行性研究", "UML", "数据流图", "用例图"]:
            if token in text:
                return token
        if any(keyword in text for keyword in ["几章", "几个章节", "目录", "课程结构"]):
            return f"{course}课程整体结构" if course != DEFAULT_VALUE else "课程整体结构"
        return DEFAULT_VALUE

    def _guess_mastery_level(self, text: str) -> str:
        lowered = str(text)
        if any(keyword in lowered for keyword in ["零基础", "刚开始", "刚入门", "一点不会", "完全不会"]):
            return "入门起步"
        if any(keyword in lowered for keyword in ["不太会", "不太懂", "模糊", "没学明白", "有点不会", "不熟"]):
            return "基础未稳"
        if any(keyword in lowered for keyword in ["会一些", "学过", "有基础", "了解过"]):
            return "有一定基础"
        if any(keyword in lowered for keyword in ["比较熟", "掌握得不错", "很熟", "能讲清"]):
            return "掌握较好"
        return DEFAULT_VALUE

    def _guess_current_difficulty(self, text: str) -> str:
        patterns = [
            r"对于[“\"']?([^，。！？\n]{2,24})[”\"']?这个部分不太会",
            r"([^，。！？\n]{2,24})不太会",
            r"([^，。！？\n]{2,24})不太懂",
            r"([^，。！？\n]{2,24})看不懂",
            r"卡在([^，。！？\n]{2,24})",
            r"不会([^，。！？\n]{2,24})",
            r"薄弱点是([^，。！？\n]{2,24})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if any(keyword in text for keyword in ["不太会", "不太懂", "困难", "模糊", "卡住", "不会"]):
            return "当前知识点理解还不稳定"
        return DEFAULT_VALUE

    def _guess_task_goal(self, text: str, course: str) -> str:
        patterns = [
            r"(?:目标|希望|想要|打算)(?:是|为)?([^，。！？\n]{4,32})",
            r"我想([^，。！？\n]{4,32})",
            r"我希望([^，。！？\n]{4,32})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if any(keyword in text for keyword in ["怎么学", "学习路线", "如何学习"]):
            return f"建立{course}的学习路径" if course != DEFAULT_VALUE else "建立当前课程的学习路径"
        if any(keyword in text for keyword in ["解释", "讲讲", "帮我理解", "图解"]):
            return "先把当前知识点讲明白"
        return DEFAULT_VALUE

    def _guess_support_preference(self, text: str) -> str:
        preferences = []
        if any(keyword in text for keyword in ["图解", "画图", "流程图", "结构图"]):
            preferences.append("图解梳理")
        if any(keyword in text for keyword in ["例子", "案例", "举例"]):
            preferences.append("案例说明")
        if any(keyword in text for keyword in ["代码", "实操", "实现"]):
            preferences.append("代码示例")
        if any(keyword in text for keyword in ["通俗", "简单", "好懂", "一步一步", "分步骤"]):
            preferences.append("通俗分步骤讲解")
        if any(keyword in text for keyword in ["题", "刷题", "练习"]):
            preferences.append("练习带动理解")
        return "、".join(preferences[:2]) if preferences else DEFAULT_VALUE

    def _guess_engagement_level(self, text: str) -> str:
        if any(keyword in text for keyword in ["刚开始", "入门", "起步"]):
            return "刚开始接触"
        if any(keyword in text for keyword in ["复习", "回顾", "巩固"]):
            return "复习巩固中"
        if any(keyword in text for keyword in ["冲刺", "考试", "期末", "考研"]):
            return "目标驱动强化中"
        if any(keyword in text for keyword in ["最近一直", "持续", "这段时间都在"]):
            return "持续学习中"
        return DEFAULT_VALUE

    def _guess_learning_background(self, text: str, mastery_level: str) -> str:
        pieces = []
        major = self._guess_major(text)
        if major != DEFAULT_VALUE:
            pieces.append(f"{major}相关背景")
        if mastery_level != DEFAULT_VALUE:
            pieces.append(f"当前处于“{mastery_level}”阶段")
        if any(keyword in text for keyword in ["学过", "接触过", "看过"]):
            pieces.append("此前接触过相关内容")
        return "；".join(pieces) if pieces else DEFAULT_VALUE

    def _guess_recent_progress(self, text: str, current_topic: str) -> str:
        match = re.search(r"(?:学到|看到|进行到)([^，。！？\n]{2,24})", text)
        if match:
            return match.group(1).strip()
        if current_topic != DEFAULT_VALUE:
            return f"当前正在围绕“{current_topic}”继续理解"
        if any(keyword in text for keyword in ["刚开始", "入门"]):
            return "刚进入课程起步阶段"
        return DEFAULT_VALUE

    def _guess_schedule_pattern(self, text: str) -> str:
        patterns = []
        if "晚上" in text or "夜里" in text or "夜间" in text:
            patterns.append("偏晚上学习")
        if "周末" in text:
            patterns.append("周末集中安排")
        if "碎片" in text:
            patterns.append("碎片化推进")
        if "固定" in text:
            patterns.append("有固定学习时段")
        return "、".join(patterns[:2]) if patterns else DEFAULT_VALUE

    def _guess_resource_preference(self, text: str) -> str:
        options = []
        if "视频" in text:
            options.append("视频讲解")
        if any(keyword in text for keyword in ["图解", "思维导图", "流程图"]):
            options.append("图解资料")
        if any(keyword in text for keyword in ["题", "练习", "刷题"]):
            options.append("练习题")
        if "代码" in text:
            options.append("代码示例")
        if any(keyword in text for keyword in ["文档", "讲义", "教材"]):
            options.append("文字资料")
        return "、".join(options[:2]) if options else DEFAULT_VALUE

    def _guess_weak_knowledge_points(self, text: str, current_difficulty: str) -> str:
        if current_difficulty != DEFAULT_VALUE:
            return current_difficulty
        for token in ["需求分析", "总体设计", "详细设计", "Scrum", "Sprint", "软件测试", "UML", "数据流图"]:
            if token in text and any(keyword in text for keyword in ["不会", "不懂", "模糊", "困难"]):
                return token
        return DEFAULT_VALUE

    def _derive_next_step(self, profile: Dict[str, str]) -> str:
        topic = self._clean_value(profile.get("current_topic"))
        difficulty = self._clean_value(profile.get("current_difficulty"))
        preference = self._clean_value(profile.get("support_preference"))
        goal = self._clean_value(profile.get("task_goal"))

        if topic != DEFAULT_VALUE and difficulty != DEFAULT_VALUE:
            return f"先围绕“{topic}”把“{difficulty}”讲透，再做1-2个小练习验证理解。"
        if topic != DEFAULT_VALUE and preference != DEFAULT_VALUE:
            return f"下一步可按“{preference}”方式继续展开“{topic}”。"
        if goal != DEFAULT_VALUE:
            return f"把当前问题拆成可执行步骤，优先推进“{goal}”。"
        return DEFAULT_VALUE

    def _confidence_label(self, profile: Dict[str, str]) -> str:
        ratio = self._confidence_by_profile(profile)
        if ratio >= 0.84:
            return "高"
        if ratio >= 0.5:
            return "中"
        return "低"

    def _build_summary(self, profile: Dict[str, str]) -> str:
        major = self._clean_value(profile.get("major"))
        course = self._clean_value(profile.get("target_course"))
        topic = self._clean_value(profile.get("current_topic"))
        mastery = self._clean_value(profile.get("mastery_level"))
        difficulty = self._clean_value(profile.get("current_difficulty"))
        goal = self._clean_value(profile.get("task_goal"))
        support = self._clean_value(profile.get("support_preference"))

        parts = []
        if major != DEFAULT_VALUE:
            parts.append(f"{major}方向")
        if course != DEFAULT_VALUE:
            parts.append(f"当前聚焦{course}")
        if topic != DEFAULT_VALUE:
            parts.append(f"正在处理“{topic}”")
        if mastery != DEFAULT_VALUE:
            parts.append(f"掌握状态：{mastery}")
        if difficulty != DEFAULT_VALUE:
            parts.append(f"主要卡点：{difficulty}")
        if goal != DEFAULT_VALUE:
            parts.append(f"当前目标：{goal}")
        if support != DEFAULT_VALUE:
            parts.append(f"更适合：{support}")

        return "；".join(parts) if parts else "继续进行真实学习对话后，这里会自动沉淀出更稳定的学生画像。"

    def _clean_value(self, value: Any) -> str:
        text = str(value or "").strip()
        if text in {"", "None", "null", "undefined", DEFAULT_VALUE}:
            return DEFAULT_VALUE
        return re.sub(r"\s+", " ", text)

    def _first_meaningful(self, *values: Any) -> str:
        for value in values:
            cleaned = self._clean_value(value)
            if cleaned != DEFAULT_VALUE:
                return cleaned
        return DEFAULT_VALUE
