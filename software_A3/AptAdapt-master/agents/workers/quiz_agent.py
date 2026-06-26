"""Quiz Agent — 生成练习题（选择题/判断题/简答题）"""
from ..state import AgentState

SYSTEM_PROMPT = """你是练习题生成智能体。请根据知识点、难度等级和学生薄弱点，生成针对性练习题。

题目类型支持：
1. 选择题 (choice)
2. 判断题 (true_false)
3. 简答题 (short_answer)

输出格式（JSON）：
{
  "type": "choice",
  "question": "题目内容",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": 0,
  "explanation": "解析说明",
  "difficulty": "medium",
  "knowledge_point": "Cache映射方式"
}
"""


def quiz_node(state: AgentState) -> AgentState:
    """生成练习题（原型）"""
    # TODO: 调用星火 API 生成实际题目
    quiz = {
        "type": "choice",
        "question": "在 Cache 映射方式中，哪种方式的冲突率最高？",
        "options": [
            "A. 直接映射",
            "B. 全相联映射",
            "C. 组相联映射",
            "D. 以上都相同"
        ],
        "answer": 0,
        "explanation": "直接映射中每个主存块只能映射到唯一的 Cache 行，当多个主存块映射到同一 Cache 行时产生冲突，因此冲突率最高。",
        "difficulty": "medium",
        "knowledge_point": "Cache映射方式"
    }

    state["quiz_data"] = quiz

    resources = state.get("generated_resources", [])
    resources.append({"type": "quiz", "title": "Cache 映射方式 练习题", "content": quiz})
    state["generated_resources"] = resources
    state["next_step"] = _next_in_sequence(state)
    return state


def _next_in_sequence(state: AgentState) -> str:
    seq = state.get("agent_sequence", [])
    current = state.get("current_agent", "")
    if current in seq:
        idx = seq.index(current)
        return seq[idx + 1] if idx + 1 < len(seq) else "end"
    return "end"
