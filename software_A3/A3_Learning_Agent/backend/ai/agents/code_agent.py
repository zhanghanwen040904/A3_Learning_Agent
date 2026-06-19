from .base_agent import XunfeiAgentSpec
from .visual_agent import VisualAgent


class CodeAgent:
    def __init__(self):
        self.role = "代码实操案例生成师"
        self.goal = "生成可运行的人工智能导论课程代码实操案例。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat"],
            input_schema="教材原文片段",
            output_schema="Python代码",
        )
        self.visual_agent = VisualAgent()

    def generate(self, knowledge_text: str) -> str:
        return self.visual_agent.generate(knowledge_text).get("code", "print('代码案例生成失败')")
