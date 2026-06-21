from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class TutorAgent:
    def __init__(self):
        self.role = "多模态智能辅导老师"
        self.goal = "严格基于课程知识库回答学生问题，并提供图解和自测。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["retrieve_knowledge", "spark_chat", "see_dance_generate"],
            input_schema="学生问题",
            output_schema="Markdown答疑 + 课程来源",
        )

    def answer(self, question: str) -> dict:
        evidence_items = retrieve_knowledge_items(question, top_k=3)
        evidence = retrieve_knowledge(question, top_k=3)
        prompt = f"""
你是人工智能导论课程智能辅导老师。请严格基于教材原文回答学生问题。
要求：先通俗解释，再给图解说明，最后给自测题。若教材依据不足，必须明确提示。
学生问题：{question}
教材原文：
{evidence}
""".strip()
        return {"answer": spark_chat(prompt), "evidence": evidence, "sources": evidence_items}
