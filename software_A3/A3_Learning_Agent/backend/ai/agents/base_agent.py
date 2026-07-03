from dataclasses import dataclass
from typing import List


@dataclass
class AgentSpec:
    """智能体元数据描述。"""

    role: str
    goal: str
    tools: List[str]
    input_schema: str
    output_schema: str

    def describe(self) -> dict:
        """导出智能体元数据。"""
        return {
            "role": self.role,
            "goal": self.goal,
            "tools": self.tools,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
