"""Reviewer Agent — 审核生成内容的事实性、安全性和完整性"""
from .state import AgentState

SYSTEM_PROMPT = """你是内容审核智能体。请对 Worker Agent 生成的内容进行审核，重点检查：

1. 事实性：内容是否与提供的知识库片段一致
2. 安全性：内容是否包含敏感或违规信息
3. 完整性：内容是否覆盖了学生问题的核心要点
4. 引用：生成结果是否标注了知识库来源

输出格式（JSON）：
{
  "passed": true/false,
  "issues": ["问题描述"],
  "suggestions": ["修改建议"],
  "referenced_chunks": ["chunk_id_1", "chunk_id_2"]
}
"""


def reviewer_node(state: AgentState) -> AgentState:
    """审核生成内容（原型）"""
    # TODO: 调用星火 API 进行实际审核
    resources = state.get("generated_resources", [])
    retrieved = state.get("retrieved_chunks", [])

    passed = True
    notes = []

    if not retrieved:
        notes.append("⚠️ 未检索到知识库片段，内容可能缺少依据")

    if not resources:
        notes.append("⚠️ 未生成任何资源")
        passed = False
    else:
        notes.append(f"已审核 {len(resources)} 个资源")

    if retrieved:
        chunk_ids = [c.get("id", "") for c in retrieved]
        notes.append(f"引用来源: {chunk_ids}")

    state["review_passed"] = passed
    state["review_notes"] = notes
    state["next_step"] = "end"

    return state
