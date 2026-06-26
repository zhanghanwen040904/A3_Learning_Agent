"""课程注册表 — 定义可切换的多门课程"""
COURSES = [
    {
        "id": "computer_organization",
        "name": "计算机组成原理",
        "icon": "cpu",
        "description": "涵盖冯诺依曼结构、Cache、流水线、中断等核心知识点",
        "chapters": [
            "计算机系统概论", "数据表示与运算", "存储器层次结构",
            "指令系统", "CPU与控制器", "流水线技术",
            "总线与I/O", "性能评价"
        ],
        "chroma_collection": "computer_organization",
        "dag_file": "knowledge_dag.json",
    },
    {
        "id": "data_structure",
        "name": "数据结构",
        "icon": "tree",
        "description": "线性表、栈、队列、树、图、排序算法等经典内容",
        "chapters": [
            "绪论", "线性表", "栈与队列", "串",
            "树与二叉树", "图", "查找", "排序"
        ],
        "chroma_collection": "data_structure",
        "dag_file": "knowledge_dag.json",
    },
    {
        "id": "operating_system",
        "name": "操作系统",
        "icon": "os",
        "description": "进程管理、内存管理、文件系统、设备管理等",
        "chapters": [
            "操作系统概述", "进程管理", "内存管理",
            "文件系统", "设备管理", "死锁"
        ],
        "chroma_collection": "operating_system",
        "dag_file": "knowledge_dag.json",
    },
    {
        "id": "computer_network",
        "name": "计算机网络",
        "icon": "network",
        "description": "TCP/IP协议栈、路由、传输层、应用层等",
        "chapters": [
            "网络概述", "物理层", "数据链路层",
            "网络层", "传输层", "应用层"
        ],
        "chroma_collection": "computer_network",
        "dag_file": "knowledge_dag.json",
    },
]

DEFAULT_COURSE = "computer_organization"


def get_course(course_id: str) -> dict | None:
    for c in COURSES:
        if c["id"] == course_id:
            return c
    return None


def get_collection_name(course_id: str) -> str:
    course = get_course(course_id)
    return course["chroma_collection"] if course else DEFAULT_COURSE
