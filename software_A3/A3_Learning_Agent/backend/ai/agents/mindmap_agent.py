from .resource_base import StructuredResourceAgent


class MindMapAgent(StructuredResourceAgent):
    resource_type = "mindmap"
    role = "知识可视化与思维导图设计师"
    goal = "把学生薄弱知识点组织成结构清晰、可交互渲染的现代 Markdown 思维导图"
    default_title = "阶段知识导图"
    requirements = """
content 必须只返回 Markdown 格式的知识点大纲，不要 JSON，不要代码围栏，不要解释。
一级标题必须是当前资源或阶段对应的具体知识主题，例如“# 需求分析”“# 软件测试”“# 软件生命周期”，不要使用“个性化知识思维导图”“软件工程知识导图”这类泛标题。
二级标题为知识模块，三级和四级标题用于继续展开具体知识点，允许超过 3 层，但必须层级清晰。
核心考点使用“⭐ ”前缀，易错点使用“⚠️ ”前缀。
内容必须严格围绕软件工程课程知识库、学生薄弱点和当前阶段知识点展开，尽量把相关知识点罗列清楚。
不能输出 center_topic、centerTheme、root、mindmap 等模板变量或 Mermaid 语法。
节点文字要短而明确，每个模块下保留 3 到 6 个关键点，避免超长句。
建议结构：核心概念、关键流程、输入输出、阶段产物、典型场景、易错提醒、学习建议。
format 必须返回 markdown。
""".strip()
 