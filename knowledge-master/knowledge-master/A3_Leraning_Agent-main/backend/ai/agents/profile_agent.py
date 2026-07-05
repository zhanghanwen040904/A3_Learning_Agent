import re
from typing import Dict

from ai.json_utils import extract_json_object
from ai.spark_api import spark_chat
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


class ProfileAgent:
    """从学生对话中提取结构化学习画像。"""

    def __init__(self):
        self.role = "学习画像分析师"
        self.goal = "从学生自然语言对话中抽取学习画像，并严格返回 JSON。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat"],
            input_schema="学生自然语言对话文本",
            output_schema='{"major":"","target_course":"","knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":"","challenge_scene":"","preferred_resource":"","profile_summary":""}',
        )

    def analyze(self, dialogue_text: str) -> Dict[str, str]:
        parsed = self._extract_from_dialogue(dialogue_text)
        if config.MOCK_AI:
            return parsed

        prompt = f"""
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

如果信息不足，请根据对话合理归纳为“{DEFAULT_VALUE}”，不要增加新字段。

学生对话：
{dialogue_text}
""".strip()
        raw = spark_chat(prompt)
        model_result = self._parse_profile(raw)
        return self._merge_profile(model_result, parsed)

    def _parse_profile(self, raw: str) -> Dict[str, str]:
        data = extract_json_object(raw)
        return {field: str(data.get(field) or DEFAULT_VALUE) for field in PROFILE_FIELDS}

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

    def _extract_by_aliases(self, text: str, aliases: list[str]) -> str:
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
        candidates = ["人工智能导论", "机器学习", "神经网络", "反向传播", "监督学习", "无监督学习"]
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
        candidates = ["监督学习和无监督学习", "反向传播", "公式推导", "做题", "代码实现", "神经网络"]
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
