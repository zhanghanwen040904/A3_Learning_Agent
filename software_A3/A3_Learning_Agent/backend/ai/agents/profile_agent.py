import json
from typing import Any, Dict

from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec

PROFILE_FIELDS = [
    "knowledge_level",
    "study_style",
    "weak_points",
    "study_goal",
    "study_time_prefer",
    "course_progress",
]


class ProfileAgent:
    """画像解析智能体。

    功能：从学生自然语言对话中抽取 6 维固定画像。
    输入：学生对话文本。
    输出：字段与 student_profile 数据库表一致的画像 JSON 字典。
    """

    def __init__(self):
        self.role = "学习画像分析师"
        self.goal = "从学生自然语言对话中抽取6维固定画像，严格返回JSON。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat"],
            input_schema="学生自然语言对话文本",
            output_schema='{"knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":""}',
        )

    def analyze(self, dialogue_text: str) -> Dict[str, str]:
        prompt = f"""
你是学习画像分析师。请从学生自然语言对话中抽取6维学生画像。
必须严格只返回JSON，不要Markdown，不要解释。
JSON字段必须完全一致：
{{"knowledge_level":"","study_style":"","weak_points":"","study_goal":"","study_time_prefer":"","course_progress":""}}
如果信息不足，请基于对话合理归纳为“待进一步观察”，不要增加新字段。
学生对话：
{dialogue_text}
""".strip()
        raw = spark_chat(prompt)
        return self._parse_profile(raw)

    def _parse_profile(self, raw: str) -> Dict[str, str]:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            data = {}
        return {field: str(data.get(field) or "待进一步观察") for field in PROFILE_FIELDS}
