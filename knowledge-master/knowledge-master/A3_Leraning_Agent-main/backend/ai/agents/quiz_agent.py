from .resource_base import StructuredResourceAgent


class QuizAgent(StructuredResourceAgent):
    resource_type = "quiz"
    role = "软件工程分层练习题设计师"
    goal = "围绕学生薄弱知识点生成可诊断、可反馈的练习题"
    default_title = "软件工程分难度练习题"
    requirements = """
content 必须包含：
## 基础题
2 道题，适合检查概念。
## 提升题
2 道题，适合比较、分析、判断。
## 应用题
1 道题，结合软件工程场景。
每题都要包含：题目、答案要点、对应知识点。
题目必须是新生成的，不要照搬教材课堂作业原文。
不要生成与软件工程无关的机器学习、鸢尾花分类等内容。
""".strip()
