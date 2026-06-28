from .resource_base import StructuredResourceAgent


class MindMapAgent(StructuredResourceAgent):
    resource_type = "mindmap"
    role = "知识可视化与思维导图设计师"
    goal = "把学生薄弱知识点组织成可渲染、层级清晰、内容详细的白蓝风格知识导图"
    default_title = "个性化知识思维导图"
    requirements = """
content 必须只返回合法 Mermaid mindmap 源码，不要 JSON，不要 Markdown 代码围栏，不要解释。
第一行必须是 mindmap，第二行必须是 root((软件工程知识导图))。
整体采用“中心主题 -> 一级模块 -> 二级知识点 -> 关键说明/易错点”的思维导图结构，不要输出 graph/tree/flowchart。
至少包含 5 个一级分支，每个一级分支至少包含 3 个二级知识点，并尽量补充关键概念、作用、输入输出、适用场景和易错点。
节点文字要短而明确，避免冒号、括号、引号、竖线、反引号、花括号等容易导致 Mermaid 报错的符号。
必须围绕软件工程课程知识库与学生薄弱点生成，不能输出空节点或只有框架。
format 必须返回 mermaid。
""".strip()
