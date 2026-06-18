from ai.spark_api import see_dance_generate
from .base_agent import XunfeiAgentSpec


class VideoAgent:
    """视频生成智能体。

    功能：基于核心知识点调用讯飞 SeeDance 生成 60 秒以内教学短视频。
    输入：知识点文本。
    输出：教学短视频 URL 或标准错误 JSON 字符串。
    """

    def __init__(self):
        self.role = "多模态视频制作师"
        self.goal = "基于单个核心知识点生成聚焦、简短、适合本科生学习的教学短视频。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["see_dance_generate"],
            input_schema="核心知识点文本",
            output_schema="教学短视频URL",
        )

    def generate(self, knowledge_text: str) -> str:
        script = f"请生成60秒以内的人工智能导论教学短视频，聚焦一个核心知识点，语言通俗，内容基于以下教材原文：{knowledge_text[:1200]}"
        return see_dance_generate(script)
