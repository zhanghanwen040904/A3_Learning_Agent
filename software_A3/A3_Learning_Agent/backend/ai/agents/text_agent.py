import json
from typing import Any, Dict

from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class TextAgent:
    """文本资源生成智能体。

    功能：基于教材原文和学生画像生成课程讲解文档、分难度练习题、拓展阅读材料。
    输入：学生画像和 RAG 检索到的教材原文。
    输出：包含 doc、quiz、reading 的 JSON 字典。
    """

    def __init__(self):
        self.role = "课程内容生成师"
        self.goal = "严格基于教材原文生成匹配学生水平的文本学习资源。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "retrieve_knowledge"],
            input_schema="学生画像JSON + RAG检索教材原文",
            output_schema='{"doc":"","quiz":"","reading":""}',
        )

    def generate(self, profile: Dict[str, Any], knowledge_text: str) -> Dict[str, str]:
        prompt = f"""
你是课程内容生成师。请严格基于【教材原文】生成3类文本资源。
禁止编造教材原文之外的知识点。难度必须匹配学生知识水平。
必须严格只返回JSON，不要Markdown包裹，不要解释。
字段：{{"doc":"课程讲解文档","quiz":"分难度练习题","reading":"拓展阅读材料"}}
学生画像：{json.dumps(profile, ensure_ascii=False)}
教材原文：
{knowledge_text}
""".strip()
        raw = spark_chat(prompt)
        return self._parse(raw)

    def _parse(self, raw: str) -> Dict[str, str]:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        except Exception:
            data = {}
        return {
            "doc": str(data.get("doc") or raw or "文本资源生成失败"),
            "quiz": str(data.get("quiz") or "练习题生成失败"),
            "reading": str(data.get("reading") or "拓展阅读生成失败"),
        }
