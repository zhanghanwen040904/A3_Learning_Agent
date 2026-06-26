import json
from typing import Any, Dict, List

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.langchain_adapter import SparkLLM
from ai.langchain_parsers import parse_json_with_fallback
from .base_agent import XunfeiAgentSpec


def build_langchain_chain(prompt: Any) -> Any:
    if prompt is None or LangChainStrOutputParser is None:
        return None
    return prompt | SparkLLM() | LangChainStrOutputParser()


RESOURCE_PROMPT_TEMPLATE = """
[RESOURCE:{resource_type}]
你是{role}。目标：{goal}
请只生成你负责的“{raw_resource_type}”资源，不要代替其他智能体。

【学生个性化上下文】
{context}

【PlannerAgent任务计划】
{task_plan}

【课程知识库依据】
{knowledge_text}

【本资源质量要求】
{requirements}

【上一轮审核意见】
{feedback}

必须严格返回JSON，不要使用Markdown代码围栏：
{{"title":"资源标题","content":"完整资源内容","knowledge_points":["知识点"],"personalization":"明确说明如何依据该学生的专业、短板、目标和偏好进行调整","format":"markdown"}}
""".strip()

RESOURCE_PROMPT = LangChainPromptTemplate.from_template(RESOURCE_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


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
            tools=["langchain_prompt", "spark_llm", "retrieve_knowledge"],
            input_schema="结构化学生画像 + 资源规划 + RAG教材片段 + 可选返工意见",
            output_schema='{"title":"","content":"","knowledge_points":[],"personalization":"","format":"markdown"}',
        )
        self.chain = build_langchain_chain(RESOURCE_PROMPT)

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        variables = {
            "resource_type": self.resource_type.upper(),
            "raw_resource_type": self.resource_type,
            "role": self.role,
            "goal": self.goal,
            "context": json.dumps(context, ensure_ascii=False),
            "task_plan": json.dumps(task_plan, ensure_ascii=False),
            "knowledge_text": knowledge_text,
            "requirements": self.requirements,
            "feedback": feedback or "首次生成，无返工意见",
        }
        if self.chain is not None:
            raw = self.chain.invoke(variables)
        else:
            raw = SparkLLM().invoke(RESOURCE_PROMPT_TEMPLATE.format(**variables))
        data = parse_json_with_fallback(raw)
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
