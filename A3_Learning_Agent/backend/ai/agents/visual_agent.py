from typing import Dict

from ai.json_utils import extract_json_object
from ai.llm_api import llm_chat
from .base_agent import AgentSpec


class VisualAgent:
    """图解与代码案例生成智能体。"""

    def __init__(self):
        self.role = "可视化设计师"
        self.goal = "将知识点转化为清晰图解与可运行代码案例"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["llm_chat"],
            input_schema="知识点文本或教材片段",
            output_schema='{"mindmap":"Markdown格式","code":"Python代码"}',
        )

    def generate(self, knowledge_text: str) -> Dict[str, str]:
        prompt = f"""
你是可视化设计师。请基于知识点文本生成思维导图和代码案例。
必须严格只返回 JSON，不要使用 Markdown 代码块，不要解释。
字段格式：{{"mindmap":"Markdown格式思维导图","code":"可直接运行的 Python 代码，含必要中文注释"}}
要求：思维导图结构清晰；代码案例聚焦单个知识点，可直接运行。
知识点文本：
{knowledge_text}
""".strip()
        raw = llm_chat(prompt)
        return self._parse(raw)

    def _parse(self, raw: str) -> Dict[str, str]:
        data = extract_json_object(raw)
        return {
            "mindmap": str(data.get("mindmap") or "# 知识点思维导图\n- 生成失败，请检查当前大模型或图解生成配置"),
            "code": str(data.get("code") or "print('代码案例生成失败，请检查当前大模型或代码生成配置')"),
        }
