from .resource_base import StructuredResourceAgent


class QuizAgent(StructuredResourceAgent):
    resource_type = "quiz"
    role = "分层多题型练习设计师"
    goal = "针对学生短板设计可诊断、可反馈的分层练习"
    default_title = "个性化分层练习题"
    requirements = """
必须包含基础、提升、应用三个层次，并覆盖选择题、判断题、简答题和应用/编程题中的至少三种。
每题必须标注难度、知识点、标准答案和解析；干扰项应针对学生常见误区设计。
""".strip()
