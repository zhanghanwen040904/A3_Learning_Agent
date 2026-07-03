import json
from typing import Any, Dict

from ai.rag import retrieve_knowledge
from ai.llm_api import llm_chat
from .base_agent import AgentSpec


class PathAgent:
    def __init__(self):
        self.role = "个性化学习路径规划师"
        self.goal = "基于画像、掌握度和课程资料生成动态学习路径。"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["llm_chat", "retrieve_knowledge"],
            input_schema="学生画像 + 掌握度 + 教材原文",
            output_schema="Markdown学习路径",
        )

    def generate(self, profile: Dict[str, Any], mastery_summary: str = "") -> str:
        query = str(profile.get("weak_points") or profile.get("study_goal") or "软件工程")
        knowledge = retrieve_knowledge(query, top_k=3)
        prompt = f"""
你是软件工程课程学习规划师。请基于学生画像、学习评估和软件工程教材原文生成个性化学习路径。
输出要求：
1. 使用普通Markdown正文，不要使用```代码围栏包裹整段内容；
2. 不要输出ASCII图、emoji或复杂表格；
3. 使用“阶段标题 + 目标 + 学习任务 + 推荐资源 + 练习方式 + 评估指标”的清晰结构；
4. 语言简洁明确，适合学生直接照着执行。
学生画像：{json.dumps(profile, ensure_ascii=False, default=str)}
学习评估：{mastery_summary or '暂无评估数据'}
教材原文：
{knowledge}
""".strip()
        return llm_chat(prompt)
