"""MindMap Agent — 生成知识点思维导图"""
from ..state import AgentState

SYSTEM_PROMPT = """你是思维导图生成智能体。请根据知识点列表和学生画像，生成 Mermaid 格式的思维导图。

输出格式为 Mermaid mindmap 语法：
mindmap
  root((知识点名称))
    子知识点1
      细节1
      细节2
    子知识点2
      细节1
      细节2
"""


def mindmap_node(state: AgentState) -> AgentState:
    """生成思维导图（原型）"""
    # TODO: 调用星火 API 生成实际导图
    mindmap = """mindmap
  root((Cache映射方式))
    直接映射
      模运算定位
      冲突率高
    全相联映射
      任意位置存放
      硬件开销大
    组相联映射
      分组映射
      折中方案"""

    state["mindmap_data"] = mindmap

    resources = state.get("generated_resources", [])
    resources.append({"type": "mindmap", "title": "Cache 映射方式思维导图", "content": mindmap})
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
