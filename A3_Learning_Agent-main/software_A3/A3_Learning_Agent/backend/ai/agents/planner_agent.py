from typing import Any, Dict, List

from .base_agent import XunfeiAgentSpec


class PlannerAgent:
    """在生成前统一确定主题、难度和六类资源之间的分工。"""

    def __init__(self):
        self.role = "个性化资源总规划师"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal="依据学生画像和教材召回结果规划六类互补资源",
            tools=["retrieve_knowledge"],
            input_schema="结构化学生上下文 + RAG来源",
            output_schema="核心主题 + 难度 + 六类任务计划",
        )

    def plan(self, context: Dict[str, Any], sources: List[dict]) -> Dict[str, Any]:
        topic = str(context.get("weak_points") or context.get("study_goal") or "课程核心知识")
        level = str(context.get("knowledge_level") or "本科入门")
        style = str(context.get("study_style") or "讲解、练习与实践结合")
        goals = {
            "doc": "建立概念框架并澄清易错点",
            "quiz": "用多题型和三级难度诊断掌握程度",
            "reading": "连接课程知识、专业场景与前沿应用",
            "mindmap": "将概念、原理、步骤和案例可视化",
            "code": "通过可运行实验把抽象原理转化为操作经验",
            "video": "用短时长脚本和分镜形成多模态讲解",
        }
        return {
            "core_topic": topic,
            "target_level": level,
            "preferred_style": style,
            "source_count": len(sources),
            "resource_tasks": [
                {"resource_type": resource_type, "goal": goal, "focus": topic}
                for resource_type, goal in goals.items()
            ],
        }
