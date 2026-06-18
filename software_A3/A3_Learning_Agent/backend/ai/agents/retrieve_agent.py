import json
from typing import Any, Dict

from ai.rag import retrieve_knowledge
from .base_agent import XunfeiAgentSpec


class RetrieveAgent:
    """课程检索智能体。

    功能：根据学生画像中的薄弱点，检索《人工智能导论》课程知识库原文片段。
    输入：学生画像 JSON 字典。
    输出：检索到的教材原文文本。
    """

    def __init__(self):
        self.role = "课程知识库检索员"
        self.goal = "根据学生薄弱知识点检索最相关的教材原文，过滤无关信息。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["retrieve_knowledge"],
            input_schema="学生画像JSON字典",
            output_schema="检索到的教材原文文本",
        )

    def retrieve(self, profile: Dict[str, Any], top_k: int = 3) -> str:
        weak_points = profile.get("weak_points") or ""
        study_goal = profile.get("study_goal") or ""
        course_progress = profile.get("course_progress") or ""
        query = " ".join([str(weak_points), str(study_goal), str(course_progress)]).strip()
        if not query:
            query = json.dumps(profile, ensure_ascii=False)
        return retrieve_knowledge(query, top_k=top_k)
