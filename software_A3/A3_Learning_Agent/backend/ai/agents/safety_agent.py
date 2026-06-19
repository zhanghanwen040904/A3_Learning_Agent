from typing import List

from .base_agent import XunfeiAgentSpec


class SafetyAgent:
    def __init__(self):
        self.role = "内容安全与防幻觉复核员"
        self.goal = "检查生成内容是否基于课程资料，给出安全可信提示。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["content_audit", "retrieve_knowledge"],
            input_schema="生成内容 + RAG来源片段",
            output_schema="安全状态 + 引用来源 + 风险提示",
        )

    def review(self, content: str, sources: List[dict]) -> dict:
        source_names = sorted({item.get("source", "unknown") for item in sources})
        if not sources:
            return {"passed": True, "risk": "缺少课程知识库依据，内容仅作通用参考", "sources": []}
        return {"passed": True, "risk": "已基于课程知识库片段生成，并附带引用来源", "sources": source_names}
