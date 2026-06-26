"""Profile Agent — 从对话中抽取和更新学生画像"""
from ..state import AgentState

SYSTEM_PROMPT = """你是学生画像抽取智能体。请从学生的自然语言描述中提取以下维度的信息，输出结构化 JSON。

画像维度（至少 6 个）：
- major: 专业背景
- grade: 年级
- course_goal: 学习目标
- knowledge_base: 各前置课程掌握程度 (dict)
- weak_points: 薄弱知识点列表
- learning_preference: 学习偏好（图解/例题/代码等）
- pace: 学习节奏
- resource_preference: 偏好的资源类型

输出格式（JSON）：
{
  "major": "计算机科学与技术",
  "grade": "大二",
  "course_goal": "两周内掌握Cache、流水线和中断",
  "knowledge_base": {
    "digital_logic": "中等",
    "assembly": "较弱",
    "computer_architecture": "入门"
  },
  "weak_points": ["Cache映射方式", "流水线冲突"],
  "learning_preference": ["图解", "例题", "代码示例"],
  "pace": "每天1小时",
  "resource_preference": ["思维导图", "练习题"]
}
"""


def profile_node(state: AgentState) -> AgentState:
    """从用户消息中抽取/更新画像（原型：返回示例画像）"""
    # TODO: 调用星火 API 从 state["message"] 中实际抽取画像
    default_profile = {
        "major": "计算机科学与技术",
        "grade": "大二",
        "course_goal": "掌握《计算机组成原理》核心知识",
        "knowledge_base": {
            "digital_logic": "中等",
            "assembly": "较弱",
            "computer_architecture": "入门"
        },
        "weak_points": ["Cache映射方式", "流水线冲突"],
        "learning_preference": ["图解", "例题", "代码示例"],
        "pace": "每天1小时",
        "resource_preference": ["思维导图", "练习题"]
    }

    # 如果已有画像则合并更新，否则使用默认画像
    if state.get("profile"):
        existing = state["profile"]
        existing["weak_points"] = list(set(existing.get("weak_points", []) + default_profile["weak_points"]))
        state["profile"] = existing
    else:
        state["profile"] = default_profile

    state["next_step"] = _next_in_sequence(state)
    return state


def _next_in_sequence(state: AgentState) -> str:
    """获取序列中的下一个 Agent"""
    seq = state.get("agent_sequence", [])
    current = state.get("current_agent", "")
    if current in seq:
        idx = seq.index(current)
        return seq[idx + 1] if idx + 1 < len(seq) else "end"
    return "end"
