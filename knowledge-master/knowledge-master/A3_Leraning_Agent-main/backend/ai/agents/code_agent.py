from .resource_base import StructuredResourceAgent


class CodeAgent(StructuredResourceAgent):
    resource_type = "code"
    role = "软件工程实操案例设计师"
    goal = "把教材知识点转化为可操作的实践任务或轻量代码示例"
    default_title = "软件工程实操案例"
    requirements = """
content 必须优先生成“实践任务模板”，除非知识点明显适合代码。
必须包含：
## 任务背景
给出一个真实软件工程场景。
## 实践步骤
列 4-6 个可执行步骤。
## 提交物
说明学生需要交什么，如需求规格说明、数据流图、模块结构图、测试用例表等。
## 评价标准
列 3-5 条评分标准。
如果生成代码，必须与软件工程相关，且说明运行环境和预期输出。
""".strip()
