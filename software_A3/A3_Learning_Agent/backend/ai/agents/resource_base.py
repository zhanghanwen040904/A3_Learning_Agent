import json
from typing import Any, Dict, List

from ai.json_utils import extract_json_object
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class StructuredResourceAgent:
    """六类资源智能体的公共协议，统一输入输出但保留独立角色与提示词。"""

    resource_type = "unknown"
    role = "学习资源生成师"
    goal = "生成个性化学习资源"
    requirements = "内容准确、清晰并适合学生当前水平。"
    default_title = "个性化学习资源"

    def __init__(self):
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "retrieve_knowledge"],
            input_schema="结构化学生画像 + 资源规划 + RAG教材片段 + 可选返工意见",
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
[RESOURCE:{self.resource_type.upper()}]
你是{self.role}。目标：{self.goal}
请只生成你负责的“{self.resource_type}”资源，不要代替其他智能体。

【学生个性化上下文】
{json.dumps(context, ensure_ascii=False)}

【PlannerAgent任务计划】
{json.dumps(task_plan, ensure_ascii=False)}

【课程知识库依据】
{knowledge_text}

【本资源质量要求】
{self.requirements}

【上一轮审核意见】
{feedback or '首次生成，无返工意见'}

必须严格返回JSON，不要使用Markdown代码围栏：
{{"title":"资源标题","content":"完整资源内容","knowledge_points":["知识点"],"personalization":"明确说明如何依据该学生的专业、短板、目标和偏好进行调整","format":"markdown"}}
""".strip()
        raw = spark_chat(prompt)
        data = extract_json_object(raw)
        content = str(data.get("content") or raw or "资源生成失败")
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
                or f"围绕学生薄弱点“{context.get('weak_points', '待观察')}”，按其学习偏好“{context.get('study_style', '综合学习')}”组织内容。"
            ),
            "format": str(data.get("format") or "markdown"),
            "agent_name": self.__class__.__name__,
        }

    @staticmethod
    def _context_points(context: Dict[str, Any]) -> List[str]:
        value = context.get("weak_points") or context.get("study_goal") or "课程核心知识"
        if isinstance(value, list):
            return value[:4]
        return [item.strip() for item in str(value).replace("，", ",").split(",") if item.strip()][:4]
