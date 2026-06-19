from .resource_base import StructuredResourceAgent


class MindMapAgent(StructuredResourceAgent):
    resource_type = "mindmap"
    role = "知识可视化与思维导图设计师"
    goal = "把学生薄弱知识点组织成可渲染、层次清晰的知识结构图"
    default_title = "个性化知识思维导图"
    requirements = """
content必须是合法Mermaid mindmap源码，以“mindmap”开头，不要包含```围栏。
根节点聚焦学生首要薄弱点，至少包含概念、原理、步骤、案例、易错点五个分支。
format必须返回mermaid。
""".strip()
