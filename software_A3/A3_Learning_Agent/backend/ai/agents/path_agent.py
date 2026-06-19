import json
from typing import Any, Dict

from ai.rag import retrieve_knowledge
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class PathAgent:
    def __init__(self):
        self.role = "个性化学习路径规划师"
        self.goal = "基于画像、掌握度和课程资料生成动态学习路径。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "retrieve_knowledge"],
            input_schema="学生画像 + 掌握度 + 教材原文",
            output_schema="Markdown学习路径",
        )

    def generate(self, profile: Dict[str, Any], mastery_summary: str = "") -> str:
        query = str(profile.get("weak_points") or profile.get("study_goal") or "人工智能导论")
        knowledge = retrieve_knowledge(query, top_k=3)
        prompt = f"""
你是人工智能导论课程学习规划师。请基于学生画像、学习评估和教材原文生成个性化学习路径。
要求包含阶段目标、推荐资源、练习任务、评估指标和动态调整建议。
学生画像：{json.dumps(profile, ensure_ascii=False, default=str)}
学习评估：{mastery_summary or '暂无评估数据'}
教材原文：
{knowledge}
""".strip()
        return spark_chat(prompt)
