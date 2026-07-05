from dataclasses import dataclass
from typing import List


@dataclass
class XunfeiAgentSpec:
    """讯飞专用智能体描述类。

    功能：保存智能体角色、目标、工具、输入和输出定义，避免 CrewAI 默认初始化 OpenAI 模型。
    输入：角色、目标、工具列表、输入说明、输出说明。
    输出：可被接口、文档和调度器读取的智能体元数据对象。
    """

    role: str
    goal: str
    tools: List[str]
    input_schema: str
    output_schema: str

    def describe(self) -> dict:
        """导出智能体元数据。

        功能：将智能体描述转换为字典，便于前端展示或文档生成。
        输入：无。
        输出：包含角色、目标、工具、输入输出的字典。
        """
        return {
            "role": self.role,
            "goal": self.goal,
            "tools": self.tools,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
