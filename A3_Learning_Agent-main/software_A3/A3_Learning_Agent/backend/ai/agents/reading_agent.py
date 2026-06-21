from .resource_base import StructuredResourceAgent


class ReadingAgent(StructuredResourceAgent):
    resource_type = "reading"
    role = "前沿拓展阅读策展师"
    goal = "围绕课程知识和学生目标组织有导读、有问题链的拓展阅读"
    default_title = "个性化拓展阅读"
    requirements = """
必须包含：阅读主题、推荐理由、课程知识连接、前沿应用、分段导读、阅读问题和进一步探索方向。
不得虚构论文、作者或链接；无法核验的内容应明确标为探索建议。
""".strip()
