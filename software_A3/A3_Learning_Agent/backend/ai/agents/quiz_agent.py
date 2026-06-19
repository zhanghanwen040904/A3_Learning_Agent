from .base_agent import XunfeiAgentSpec
from .text_agent import TextAgent


class QuizAgent:
    def __init__(self):
        self.role = "分层练习设计师"
        self.goal = "根据画像和教材设计基础、提升、应用三个层次练习。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "retrieve_knowledge"],
            input_schema="学生画像 + 教材原文",
            output_schema="分层练习题Markdown",
        )
        self.text_agent = TextAgent()

    def generate(self, profile, knowledge_text: str) -> str:
        return self.text_agent.generate(profile, knowledge_text).get("quiz", "练习题生成失败")
