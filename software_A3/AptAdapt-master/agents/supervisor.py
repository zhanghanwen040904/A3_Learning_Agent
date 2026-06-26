"""Supervisor Agent — 任务识别、路由分发、流程编排"""
from .state import AgentState


SYSTEM_PROMPT = """你是 AptAdapt 系统的 Supervisor 智能体，负责识别学生意图并调度 Worker Agent。

你的职责：
1. 分析用户输入，判断任务类型
2. 决定需要调用哪些 Agent，以及调用顺序
3. 将任务分发给对应的 Worker Agent

任务类型：
- profile: 抽取/更新学生画像
- doc: 生成讲解文档
- mindmap: 生成思维导图
- quiz: 生成练习题
- code: 生成代码案例
- video_script: 生成视频脚本
- path: 规划学习路径

输出格式（JSON）：
{
  "task_type": "doc",
  "agent_sequence": ["profile", "doc", "reviewer"],
  "reasoning": "学生询问Cache映射方式，需要先更新画像，生成讲解文档，最后审核"
}
"""


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor 节点：分析用户意图，决定任务路由。

    当前为原型实现，后续接入星火 API 进行意图识别。
    """
    message = state.get("message", "")

    # 原型路由逻辑（后续由 LLM 替代）
    if any(kw in message for kw in ["我是", "专业", "基础", "学过", "薄弱", "目标"]):
        task_type = "profile"
        agent_sequence = ["profile"]
    elif any(kw in message for kw in ["题目", "练习题", "测试", "做题"]):
        task_type = "quiz"
        agent_sequence = ["quiz", "reviewer"]
    elif any(kw in message for kw in ["代码", "verilog", "汇编", "Verilog"]):
        task_type = "code"
        agent_sequence = ["code", "reviewer"]
    elif any(kw in message for kw in ["路径", "计划", "学习顺序", "规划"]):
        task_type = "path"
        agent_sequence = ["planner"]
    elif any(kw in message for kw in ["导图", "思维导图", "脑图"]):
        task_type = "mindmap"
        agent_sequence = ["mindmap", "reviewer"]
    elif any(kw in message for kw in ["视频", "脚本", "讲解视频"]):
        task_type = "video_script"
        agent_sequence = ["video_script", "reviewer"]
    else:
        # 默认生成讲解文档
        task_type = "doc"
        agent_sequence = ["profile", "retrieve", "doc", "reviewer"]

    state["task_type"] = task_type
    state["agent_sequence"] = agent_sequence
    state["current_agent"] = agent_sequence[0] if agent_sequence else None
    state["next_step"] = agent_sequence[0] if agent_sequence else "end"

    return state


def should_continue(state: AgentState) -> str:
    """判断流程是否继续或结束"""
    if state.get("error"):
        return "end"
    if state.get("next_step") == "end":
        return "end"
    return state.get("next_step", "end")
