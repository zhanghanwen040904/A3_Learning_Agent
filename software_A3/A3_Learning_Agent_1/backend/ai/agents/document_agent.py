from .resource_base import StructuredResourceAgent


class DocumentAgent(StructuredResourceAgent):
    resource_type = "doc"
    role = "专业课程讲解文档生成师"
    goal = "把教材知识转化为适合学生当前基础的递进式专业课程讲解"
    default_title = "个性化课程讲解文档"
    requirements = """
必须包含：学习目标、前置知识、概念讲解、与学生专业相关的案例、易错点、三问自测和总结。
讲解难度必须匹配画像；关键事实须能由课程知识库支持；正文不少于500字。
""".strip()
