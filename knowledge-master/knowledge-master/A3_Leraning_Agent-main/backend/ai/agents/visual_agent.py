from typing import Dict

from ai.json_utils import extract_json_object
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class VisualAgent:
    """可视化生成智能体。

    功能：基于知识点文本生成 Markdown 思维导图和可运行 Python 代码案例。
    输入：知识点文本。
    输出：包含 mindmap 和 code 的 JSON 字典。
    """

    def __init__(self):
        self.role = "可视化设计师"
        self.goal = "将抽象知识点转化为清晰思维导图和可运行代码案例。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat"],
            input_schema="知识点文本或教材原文片段",
            output_schema='{"mindmap":"Markdown格式","code":"Python代码"}',
        )

    def generate(self, knowledge_text: str) -> Dict[str, str]:
        prompt = f"""
你是可视化设计师。请基于知识点文本生成思维导图和代码案例。
必须严格只返回JSON，不要Markdown包裹，不要解释。
字段：{{"mindmap":"Markdown格式思维导图","code":"可直接运行的Python代码，含必要中文注释"}}
要求：思维导图结构清晰；代码案例聚焦单个人工智能导论知识点，可直接运行。
知识点文本：
{knowledge_text}
""".strip()
        raw = spark_chat(prompt)
        return self._parse(raw)

    def _parse(self, raw: str) -> Dict[str, str]:
        data = extract_json_object(raw)
        return {
            "mindmap": str(data.get("mindmap") or "# 知识点思维导图\n- 生成失败，请检查讯飞星火配置"),
            "code": str(data.get("code") or "print('代码案例生成失败，请检查讯飞星火配置')"),
        }
