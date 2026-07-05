import json
from typing import Any, Dict, List

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.llm_adapter import PlatformLLM
from ai.langchain_parsers import parse_json_with_fallback
from .base_agent import AgentSpec


PLANNER_PROMPT_TEMPLATE = """
你是个性化资源总规划师。请基于学生画像和课程知识库召回来源，为六类资源生成任务规划。

要求：
1. 严格返回 JSON，不要 Markdown，不要解释；
2. core_topic 聚焦学生当前最需要解决的知识点；
3. target_level 要根据学生基础调整；
4. preferred_style 要体现学生学习偏好；
5. resource_tasks 必须包含 doc、quiz、reading、mindmap、code、video 六类资源；
6. 每类任务需要包含 resource_type、goal、focus 三个字段。

学生上下文：
{context}

课程知识库来源：
{sources}

返回格式：
{{
  "core_topic": "",
  "target_level": "",
  "preferred_style": "",
  "source_count": 0,
  "resource_tasks": [
    {{"resource_type": "doc", "goal": "", "focus": ""}},
    {{"resource_type": "quiz", "goal": "", "focus": ""}},
    {{"resource_type": "reading", "goal": "", "focus": ""}},
    {{"resource_type": "mindmap", "goal": "", "focus": ""}},
    {{"resource_type": "code", "goal": "", "focus": ""}},
    {{"resource_type": "video", "goal": "", "focus": ""}}
  ]
}}
""".strip()

PLANNER_PROMPT = LangChainPromptTemplate.from_template(PLANNER_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class PlannerAgent:
    """在生成前统一确定主题、难度和六类资源之间的分工。"""

    def __init__(self):
        self.role = "个性化资源总规划师"
        self.agent = AgentSpec(
            role=self.role,
            goal="依据学生画像和教材召回结果规划六类互补资源",
            tools=["langchain_prompt", "platform_llm", "retrieve_knowledge"],
            input_schema="结构化学生上下文 + RAG来源",
            output_schema="核心主题 + 难度 + 六类任务计划",
        )
        self.chain = (PLANNER_PROMPT | PlatformLLM() | LangChainStrOutputParser()) if PLANNER_PROMPT is not None and LangChainStrOutputParser is not None else None

    def plan(self, context: Dict[str, Any], sources: List[dict]) -> Dict[str, Any]:
        fallback = self._fallback_plan(context, sources)
        variables = {
            "context": json.dumps(context, ensure_ascii=False, default=str),
            "sources": json.dumps(sources, ensure_ascii=False, default=str),
        }
        try:
            if self.chain is not None:
                raw = self.chain.invoke(variables)
            else:
                raw = PlatformLLM().invoke(PLANNER_PROMPT_TEMPLATE.format(**variables))
            data = parse_json_with_fallback(raw)
            return self._normalize_plan(data, fallback)
        except Exception:
            return fallback

    def _fallback_plan(self, context: Dict[str, Any], sources: List[dict]) -> Dict[str, Any]:
        topic = str(context.get("weak_points") or context.get("study_goal") or "课程核心知识")
        level = str(context.get("knowledge_level") or "本科入门")
        style = str(context.get("study_style") or "讲解、练习与实践结合")
        goals = {
            "doc": "建立概念框架并澄清易错点",
            "quiz": "用多题型和三级难度诊断掌握程度",
            "reading": "连接课程知识、专业场景与前沿应用",
            "mindmap": "将概念、原理、步骤和案例可视化",
            "code": "通过可运行实验把抽象原理转化为操作经验",
            "video": "用短时长脚本和分镜形成多模态讲解",
        }
        return {
            "core_topic": topic,
            "target_level": level,
            "preferred_style": style,
            "source_count": len(sources),
            "resource_tasks": [
                {"resource_type": resource_type, "goal": goal, "focus": topic}
                for resource_type, goal in goals.items()
            ],
        }

    def _normalize_plan(self, data: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        required_types = ["doc", "quiz", "reading", "mindmap", "code", "video"]
        tasks = data.get("resource_tasks") if isinstance(data.get("resource_tasks"), list) else []
        task_map = {str(item.get("resource_type")): item for item in tasks if isinstance(item, dict)}
        normalized_tasks = []
        fallback_map = {item["resource_type"]: item for item in fallback["resource_tasks"]}
        for resource_type in required_types:
            item = task_map.get(resource_type) or fallback_map[resource_type]
            normalized_tasks.append(
                {
                    "resource_type": resource_type,
                    "goal": str(item.get("goal") or fallback_map[resource_type]["goal"]),
                    "focus": str(item.get("focus") or data.get("core_topic") or fallback["core_topic"]),
                }
            )
        return {
            "core_topic": str(data.get("core_topic") or fallback["core_topic"]),
            "target_level": str(data.get("target_level") or fallback["target_level"]),
            "preferred_style": str(data.get("preferred_style") or fallback["preferred_style"]),
            "source_count": int(data.get("source_count") or fallback["source_count"]),
            "resource_tasks": normalized_tasks,
        }
