"""Code Agent — 生成 Verilog/汇编/伪代码示例"""
from ..state import AgentState

SYSTEM_PROMPT = """你是代码案例生成智能体。请根据知识点和学生画像，生成 Verilog/汇编/伪代码示例，并附带逐行解释。

输出格式（JSON）：
{
  "language": "verilog",
  "source": "代码内容",
  "explanation": "逐行解释"
}
"""


def code_node(state: AgentState) -> AgentState:
    """生成代码案例（原型）"""
    # TODO: 调用星火 API 生成实际代码
    code = {
        "language": "verilog",
        "source": """// 简单 ALU 模块
module alu (
    input  [7:0] a, b,
    input  [1:0] op,
    output reg [7:0] result
);
    always @(*) begin
        case (op)
            2'b00: result = a + b;
            2'b01: result = a - b;
            2'b10: result = a & b;
            2'b11: result = a | b;
        endcase
    end
endmodule""",
        "explanation": "该 Verilog 代码实现了一个 8 位 ALU，支持加、减、与、或四种运算。case 语句根据 op 信号选择运算类型。"
    }

    state["code_data"] = code

    resources = state.get("generated_resources", [])
    resources.append({"type": "code", "title": "ALU Verilog 示例", "content": code})
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
