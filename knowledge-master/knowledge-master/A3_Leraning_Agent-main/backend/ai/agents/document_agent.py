from .resource_base import StructuredResourceAgent


class DocumentAgent(StructuredResourceAgent):
    resource_type = "doc"
    role = "软件工程课程讲解文档生成师"
    goal = "把教材知识点转化为简明、递进、适合学生直接学习的课程讲解"
    default_title = "软件工程课程讲解文档"
    requirements = """
content 必须包含：
## 本节要学什么
用 2-3 句话说清目标。
## 核心知识点
列 3-5 个知识点，每个知识点用通俗语言解释。
## 推荐学习顺序
结合知识树关系说明先学什么、再学什么。
## 易错提醒
列 2-3 条常见误区。
## 配图说明
如有图片，输出配图建议；没有则说明暂无可用配图。
整体控制在 300-700 字，清楚、自然，不堆砌章节来源。
""".strip()
