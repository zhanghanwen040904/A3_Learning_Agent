"""VideoScript Agent — 生成短视频讲解脚本和分镜"""
from ..state import AgentState

SYSTEM_PROMPT = """你是视频脚本生成智能体。请根据知识点和学生偏好，生成 1-3 分钟的短视频讲解脚本。

输出格式（Markdown）：
## 视频标题
### 第 N 镜（N 秒）
- 画面：...
- 旁白：...
"""


def video_script_node(state: AgentState) -> AgentState:
    """生成视频脚本（原型）"""
    # TODO: 调用星火 API 生成实际脚本
    script = """## Cache 映射方式 — 3 分钟讲解

### 第 1 镜（15 秒）
- 画面：Cache 与主存交互的动画示意图
- 旁白：同学们好，今天我们来学习 Cache 的三种映射方式。

### 第 2 镜（45 秒）
- 画面：直接映射示意图，动画展示模运算过程
- 旁白：首先是直接映射，每个主存块只能映射到唯一的 Cache 行...

### 第 3 镜（45 秒）
- 画面：全相联映射与组相联映射对比图
- 旁白：全相联映射允许任意位置存放，但硬件开销大...

### 第 4 镜（30 秒）
- 画面：三种映射方式对比表格
- 旁白：总结一下，组相联映射是折中方案，也是现代处理器最常用的方式。"""

    state["video_script"] = script

    resources = state.get("generated_resources", [])
    resources.append({"type": "video_script", "title": "Cache 映射方式视频脚本", "content": script})
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
