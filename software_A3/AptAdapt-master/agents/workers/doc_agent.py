"""Doc Agent — 生成个性化讲解文档"""
from ..state import AgentState

SYSTEM_PROMPT = """你是《计算机组成原理》课程讲解智能体。请根据学生的画像和课程知识库片段，生成个性化 Markdown 讲解文档。

要求：
1. 内容必须基于提供的知识库片段，不得虚构
2. 根据学生画像调整讲解深度和风格
3. 使用 Markdown 格式，包含标题、正文、要点总结
4. 对薄弱知识点增加图解和例题说明
5. 标注引用来源（知识库片段 ID）
"""


def doc_node(state: AgentState) -> AgentState:
    """生成讲解文档（原型）"""
    # TODO: 调用星火 API + 检索片段生成实际文档
    doc = {
        "type": "doc",
        "title": f"《计算机组成原理》个性化讲解",
        "content": """## 知识点讲解

> 基于你的学习画像，以下是针对性的讲解内容。

### 核心概念

（此处将由 AI 基于知识库片段生成个性化讲解）

### 要点总结

- 关键概念 1
- 关键概念 2

### 引用来源

- 知识片段: course_chunk_001
"""
    }

    resources = state.get("generated_resources", [])
    resources.append(doc)
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
