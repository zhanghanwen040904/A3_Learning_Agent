from .resource_base import StructuredResourceAgent


class ReadingAgent(StructuredResourceAgent):
    resource_type = "reading"
    role = "软件工程拓展阅读策划师"
    goal = "围绕教材知识点设计有顺序、有问题链的拓展阅读"
    default_title = "软件工程拓展阅读材料"
    requirements = """
content 必须包含：
## 拓展阅读建议
列 3 个阅读主题，每个主题说明为什么读、关联哪个知识点。
## 阅读顺序
给出先后顺序，说明原因。
## 阅读时思考
列 3 个引导问题。
不得虚构论文、作者、链接；没有可靠来源时用“探索建议”表述。
""".strip()
