import json
from typing import Any, Dict, List

from ai.json_utils import extract_json_object
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class StructuredResourceAgent:
    """Common protocol for the six resource generation agents."""

    resource_type = "unknown"
    role = "学习资源生成师"
    goal = "基于本地软件工程知识库生成个性化学习资源"
    requirements = "内容准确、简洁、清楚，适合学生直接学习。"
    default_title = "个性化学习资源"
    output_format = "markdown"

    def __init__(self):
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "retrieve_knowledge"],
            input_schema="学生画像 + 资源规划 + 本地知识库上下文",
            output_schema='{"title":"","content":"","knowledge_points":[],"personalization":"","format":"markdown"}',
        )

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        prompt = f"""
你是{self.role}，只负责生成 {self.resource_type} 类型学习资源。

必须依据【本地知识库上下文】生成，不能编造教材中不存在的知识点、页码、图片路径或事实。
如果知识库覆盖不足，请明确写“当前知识库未覆盖”。

输出必须是一个 JSON 对象，不要 Markdown 代码块，不要解释：
{{
  "title": "简短明确的资源标题",
  "content": "完整资源内容，使用 Markdown，语言简单流畅",
  "knowledge_points": ["知识点1", "知识点2"],
  "personalization": "说明如何结合学生画像调整内容",
  "format": "{self.output_format}"
}}

通用写作要求：
1. 不要输出 chunk_id、score、retrieval_mode、JSON 字段名等内部信息。
2. 不要把大量来源路径堆给学生，最多在内容末尾用“依据：章节/页码”简短说明。
3. 内容要像老师讲课，先说要学什么，再讲重点，再给行动建议。
4. 如果上下文包含图片，必须写“配图建议：图片说明（图片路径）”。
5. 如果没有图片，写“本知识点暂无可用配图”，不要虚构。

本资源特殊要求：
{self.requirements}

学生画像：
{json.dumps(context, ensure_ascii=False, indent=2)}

PlannerAgent 任务：
{json.dumps(task_plan, ensure_ascii=False, indent=2)}

本地知识库上下文：
{knowledge_text}

上一轮质量反馈：
{feedback or "首次生成，无返工意见"}
""".strip()
        raw = spark_chat(prompt)
        data = extract_json_object(raw)
        content = str(data.get("content") or raw or "资源生成失败，请检查大模型配置。").strip()
        points = data.get("knowledge_points") or self._context_points(context)
        if not isinstance(points, list):
            points = [str(points)]
        return {
            "resource_type": self.resource_type,
            "title": str(data.get("title") or self.default_title),
            "content": content,
            "knowledge_points": [str(item) for item in points if str(item).strip()],
            "personalization": str(
                data.get("personalization")
                or f"围绕学生薄弱点“{context.get('weak_points', '待观察')}”和目标“{context.get('study_goal', '待明确')}”生成。"
            ),
            "format": str(data.get("format") or self.output_format),
            "agent_name": self.__class__.__name__,
        }

    @staticmethod
    def _context_points(context: Dict[str, Any]) -> List[str]:
        value = context.get("weak_points") or context.get("study_goal") or "软件工程核心知识"
        if isinstance(value, list):
            return [str(item) for item in value[:4]]
        return [item.strip() for item in str(value).replace("；", ",").replace("，", ",").split(",") if item.strip()][:4]
