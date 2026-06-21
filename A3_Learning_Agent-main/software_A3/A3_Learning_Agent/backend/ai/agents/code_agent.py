from .resource_base import StructuredResourceAgent


class CodeAgent(StructuredResourceAgent):
    resource_type = "code"
    role = "代码实操案例工程师"
    goal = "生成与学生专业和薄弱点相关、可运行且可继续探索的代码实验"
    default_title = "个性化代码实操案例"
    requirements = """
必须包含：学习目标、运行环境、依赖、完整Python代码、预期输出、代码讲解、修改任务和常见错误。
代码优先使用常见依赖，设置随机种子，不访问网络，不读写用户文件，并与课程知识点直接相关。
""".strip()
