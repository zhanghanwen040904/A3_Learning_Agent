from typing import List

from ai.llm_api import audit_content
from .base_agent import AgentSpec


class SafetyAgent:
    def __init__(self):
        self.role = "内容安全与防幻觉复核员"
        self.goal = "检查生成内容是否基于课程资料，给出安全可信提示。"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["audit_content", "retrieve_knowledge"],
            input_schema="生成内容 + RAG来源片段",
            output_schema="安全状态 + 引用来源 + 风险提示",
        )

    def review(self, content: str, sources: List[dict]) -> dict:
        source_names = sorted({item.get("source", "unknown") for item in sources})
        problems = []
        if not sources:
            problems.append("缺少课程知识库依据")
        if not audit_content(content):
            problems.append("内容安全审核未通过")
        passed = not problems
        return {
            "passed": passed,
            "risk": "未发现明显风险" if passed else "；".join(problems),
            "sources": source_names,
            "checks": {
                "has_course_sources": bool(sources),
                "audit_content_passed": audit_content(content),
            },
        }
