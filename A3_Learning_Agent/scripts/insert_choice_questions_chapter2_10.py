import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = PROJECT_ROOT / "rag_data"
QUESTION_PATH = next((RAG_ROOT / "questions_json").glob("*.json"))
QUESTION_BANK_PATH = next((RAG_ROOT / "question_bank_json").glob("*.json"))
STUDENT_KB_PATH = next((RAG_ROOT / "student_knowledge_base_json").glob("*.json"))


def resolve_primary_knowledge_path() -> Path:
    candidates = [
        path
        for path in (RAG_ROOT / "knowledge_points_json").glob("*.json")
        if ".bak_" not in path.name
    ]
    ranked = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            points = payload.get("knowledge_points", []) if isinstance(payload, dict) else []
            ranked.append((len(points), os.path.getsize(path), path))
        except Exception:
            continue
    if not ranked:
        raise FileNotFoundError("no usable knowledge_points_json file found")
    ranked.sort(reverse=True)
    return ranked[0][2]


KNOWLEDGE_PATH = resolve_primary_knowledge_path()


CHAPTERS = {
    2: {
        "title": "结构化分析",
        "start_no": 12,
        "questions": [
            {
                "stem": "下列关于数据流图的说法，哪一项是正确的？",
                "options": [
                    "A. 数据流图主要描述程序的控制转移顺序",
                    "B. 数据流图主要描述数据在系统中的流动和处理",
                    "C. 数据流图只能用于编码阶段",
                    "D. 数据流图与数据字典没有关系",
                ],
                "answer": "B",
                "analysis": "数据流图关注的是数据从哪里来、经过哪些处理、到哪里去，核心是描述系统的数据流动和功能处理，而不是控制流程。",
                "knowledge": ["数 据 流 图", "导出系统的逻辑模型"],
                "keywords": ["数据流图", "数据流", "逻辑模型", "结构化分析"],
            },
            {
                "stem": "在实体-联系图中，用来表示现实世界中可区分事物的是哪一项？",
                "options": [
                    "A. 实体",
                    "B. 联系",
                    "C. 属性值",
                    "D. 数据流",
                ],
                "answer": "A",
                "analysis": "ER 模型中实体表示现实世界中可以相互区分并需要描述的对象，如学生、课程、订单等。",
                "knowledge": ["实体-联系图", "数据对象"],
                "keywords": ["ER图", "实体", "数据对象", "结构化分析"],
            },
            {
                "stem": "数据字典在结构化分析中的主要作用是下列哪一项？",
                "options": [
                    "A. 用于记录程序调试步骤",
                    "B. 用于统一定义数据流、数据项和数据存储的含义",
                    "C. 用于直接生成数据库代码",
                    "D. 用于替代状态转换图",
                ],
                "answer": "B",
                "analysis": "数据字典的核心作用是对分析阶段出现的数据元素进行统一、精确的定义，减少歧义。",
                "knowledge": ["数 据 字 典", "定义数据的方法", "数据字典的内容"],
                "keywords": ["数据字典", "数据定义", "结构化分析"],
            },
            {
                "stem": "状态转换图最适合描述下列哪一类问题？",
                "options": [
                    "A. 只涉及静态数据结构的问题",
                    "B. 需要描述对象或系统随事件变化而发生状态迁移的问题",
                    "C. 只涉及算法时间复杂度的问题",
                    "D. 只涉及数据库表设计的问题",
                ],
                "answer": "B",
                "analysis": "状态转换图强调状态、事件和状态迁移，适合描述系统的动态行为。",
                "knowledge": ["状态转换图", "状态", "事件"],
                "keywords": ["状态转换图", "状态", "事件", "动态行为"],
            },
            {
                "stem": "采用面向数据流自顶向下求精的方法，其核心思想是下列哪一项？",
                "options": [
                    "A. 从代码细节开始逐步汇总系统结构",
                    "B. 从系统总体功能出发，逐步分解为更细的处理和数据流",
                    "C. 先实现数据库，再补需求文档",
                    "D. 先设计界面，再决定系统功能",
                ],
                "answer": "B",
                "analysis": "自顶向下求精强调先把握系统总体，再逐层细化功能和数据处理过程。",
                "knowledge": ["面向数据流自顶向下求精", "需 求 分 析"],
                "keywords": ["自顶向下求精", "数据流", "需求分析"],
            },
        ],
    },
    3: {
        "title": "结构化设计",
        "start_no": 16,
        "questions": [
            {
                "stem": "逐步求精的主要含义是下列哪一项？",
                "options": [
                    "A. 直接从最底层模块开始编码",
                    "B. 从高层抽象出发，逐层细化到可实现的设计细节",
                    "C. 只对界面进行细化",
                    "D. 只用于测试阶段",
                ],
                "answer": "B",
                "analysis": "逐步求精要求先解决高层问题，再逐层分解和细化，直到得到足够具体的设计。",
                "knowledge": ["逐步求精", "设计过程"],
                "keywords": ["逐步求精", "设计过程", "结构化设计"],
            },
            {
                "stem": "模块独立强调的核心目标是下列哪一项？",
                "options": [
                    "A. 提高模块间耦合并减少模块数",
                    "B. 模块内部尽量低内聚、外部尽量高耦合",
                    "C. 模块内部高内聚、模块之间低耦合",
                    "D. 所有功能集中到一个总控模块中",
                ],
                "answer": "C",
                "analysis": "模块独立的基本目标是高内聚、低耦合，以提升理解、测试和维护效率。",
                "knowledge": ["模块独立", "模块化"],
                "keywords": ["模块独立", "高内聚", "低耦合", "模块化"],
            },
            {
                "stem": "在结构化设计中，层次图和 HIPO 图主要用于下列哪一项？",
                "options": [
                    "A. 描述模块层次和调用关系",
                    "B. 描述程序运行时内存分配",
                    "C. 描述数据库索引策略",
                    "D. 描述单元测试用例",
                ],
                "answer": "A",
                "analysis": "层次图和 HIPO 图用于描绘系统模块的层次组织及控制关系。",
                "knowledge": ["层次图和 HIPO 图", "结构图"],
                "keywords": ["层次图", "HIPO图", "结构图", "模块层次"],
            },
            {
                "stem": "面向数据流的设计方法中，变换分析适用于下列哪一类数据流特征？",
                "options": [
                    "A. 输入经过中心变换后形成输出的变换流",
                    "B. 只有一个状态、没有输入输出的系统",
                    "C. 完全随机、没有数据流特征的系统",
                    "D. 仅用于面向对象类层次设计",
                ],
                "answer": "A",
                "analysis": "变换分析适用于具有输入流、变换中心、输出流的典型变换型数据流。",
                "knowledge": ["面向数据流的设计方法", "变换分析"],
                "keywords": ["面向数据流设计", "变换分析", "结构化设计"],
            },
            {
                "stem": "设计优化在结构化设计中的主要目的是什么？",
                "options": [
                    "A. 让模块关系更复杂以增加灵活性",
                    "B. 在满足功能前提下改进结构质量与实现效率",
                    "C. 删除所有中间模块",
                    "D. 用流程图替代全部设计文档",
                ],
                "answer": "B",
                "analysis": "设计优化是在正确实现功能的前提下，改进模块结构、可维护性以及时间空间效率。",
                "knowledge": ["设计优化", "设计原理"],
                "keywords": ["设计优化", "结构质量", "效率", "结构化设计"],
            },
        ],
    },
    4: {
        "title": "结构化实现",
        "start_no": 13,
        "questions": [
            {
                "stem": "选择程序设计语言时，下面哪一项通常不是主要考虑因素？",
                "options": [
                    "A. 问题领域和应用类型",
                    "B. 团队经验和工具支持",
                    "C. 语言对可靠性和可维护性的影响",
                    "D. 开发者个人当天的情绪",
                ],
                "answer": "D",
                "analysis": "语言选择应基于问题领域、团队能力、工具链、性能和维护性等工程因素，而不是个人情绪。",
                "knowledge": ["选择程序设计语言", "编码风格"],
                "keywords": ["程序设计语言", "编码风格", "结构化实现"],
            },
            {
                "stem": "白盒测试技术主要依据下列哪一项设计测试用例？",
                "options": [
                    "A. 用户对界面的主观偏好",
                    "B. 程序的内部逻辑结构",
                    "C. 市场推广计划",
                    "D. 项目预算表",
                ],
                "answer": "B",
                "analysis": "白盒测试关注程序内部控制结构、判定和路径，依据代码逻辑设计测试用例。",
                "knowledge": ["白盒测试技术", "逻辑覆盖", "控制结构测试"],
                "keywords": ["白盒测试", "逻辑覆盖", "控制结构测试"],
            },
            {
                "stem": "等价划分属于下列哪一类测试技术？",
                "options": [
                    "A. 黑盒测试技术",
                    "B. 白盒测试技术",
                    "C. 形式化证明技术",
                    "D. 配置管理技术",
                ],
                "answer": "A",
                "analysis": "等价划分和边界值分析都属于黑盒测试技术，重点从输入域角度设计测试用例。",
                "knowledge": ["黑盒测试技术", "等价划分", "边界值分析"],
                "keywords": ["黑盒测试", "等价划分", "边界值分析"],
            },
            {
                "stem": "软件测试的目标更准确地说是下列哪一项？",
                "options": [
                    "A. 证明程序绝对没有错误",
                    "B. 尽可能发现程序中的错误",
                    "C. 缩短所有文档编写时间",
                    "D. 只验证程序能成功编译",
                ],
                "answer": "B",
                "analysis": "测试不能证明程序绝对正确，但可以通过设计有效用例尽可能暴露缺陷。",
                "knowledge": ["软件测试基础", "软件测试的目标", "软件测试准则"],
                "keywords": ["软件测试", "测试目标", "测试准则"],
            },
            {
                "stem": "边界值分析之所以重要，主要是因为下列哪一项？",
                "options": [
                    "A. 边界附近通常更容易出现错误",
                    "B. 边界值测试可以替代全部其他测试",
                    "C. 边界值只和数据库设计有关",
                    "D. 边界值分析只适用于面向对象语言",
                ],
                "answer": "A",
                "analysis": "许多缺陷集中出现在输入范围的边界附近，因此边界值分析是高收益的黑盒测试方法。",
                "knowledge": ["边界值分析", "黑盒测试技术"],
                "keywords": ["边界值分析", "黑盒测试", "测试方法"],
            },
        ],
    },
    5: {
        "title": "维护",
        "start_no": 7,
        "questions": [
            {
                "stem": "下列哪一项最符合软件维护的定义？",
                "options": [
                    "A. 只在软件交付前修改编码错误",
                    "B. 软件交付使用后，为改正错误或适应变化而进行的修改活动",
                    "C. 只包括数据库备份工作",
                    "D. 只包括更换硬件设备",
                ],
                "answer": "B",
                "analysis": "软件维护发生在交付之后，既包括改错，也包括适应环境变化和完善功能等工作。",
                "knowledge": ["软件维护的定义", "维护的代价高昂"],
                "keywords": ["软件维护", "维护定义", "交付后修改"],
            },
            {
                "stem": "软件维护成本通常较高，主要原因之一是下列哪一项？",
                "options": [
                    "A. 维护不需要理解原系统",
                    "B. 维护前通常必须重新理解需求、设计和代码",
                    "C. 维护后不需要回归测试",
                    "D. 维护只修改注释，不改代码",
                ],
                "answer": "B",
                "analysis": "维护成本高的重要原因是理解旧系统本身就很耗时，且修改后还要验证没有引入新的问题。",
                "knowledge": ["维护的代价高昂", "维护的问题很多"],
                "keywords": ["维护成本", "理解旧系统", "回归测试"],
            },
            {
                "stem": "下列哪一项最能直接提高软件的可维护性？",
                "options": [
                    "A. 减少文档并增加隐式约定",
                    "B. 提高代码可读性并保持设计结构清晰",
                    "C. 尽量使用难懂但极端优化的写法",
                    "D. 取消所有模块划分",
                ],
                "answer": "B",
                "analysis": "可维护性依赖于易理解、易修改、易测试的系统结构，清晰设计和可读代码是基础。",
                "knowledge": ["软件的可维护性", "决定软件可维护性的因素"],
                "keywords": ["可维护性", "代码可读性", "设计结构"],
            },
            {
                "stem": "预防性维护的主要目的是哪一项？",
                "options": [
                    "A. 立即增加新业务功能",
                    "B. 在问题发生前改善系统结构，降低未来维护风险",
                    "C. 替代全部测试活动",
                    "D. 只修复已经出现的线上故障",
                ],
                "answer": "B",
                "analysis": "预防性维护强调提前改进系统质量，防止将来因结构劣化导致维护困难和故障增加。",
                "knowledge": ["预防性维护", "软件的可维护性"],
                "keywords": ["预防性维护", "维护风险", "系统结构"],
            },
            {
                "stem": "软件再工程更接近下列哪一项描述？",
                "options": [
                    "A. 完全放弃旧系统，不分析任何已有资产",
                    "B. 基于已有系统进行分析、重构和改造，以提高质量和延长寿命",
                    "C. 只更换操作系统而不处理软件本身",
                    "D. 只把注释翻译成另一种语言",
                ],
                "answer": "B",
                "analysis": "软件再工程是对已有系统进行理解、改造和重建，以改善结构、维护性和继续使用价值。",
                "knowledge": ["软件再工程过程", "预防性维护"],
                "keywords": ["软件再工程", "系统改造", "维护"],
            },
        ],
    },
    6: {
        "title": "面向对象方法学引论",
        "start_no": 11,
        "questions": [
            {
                "stem": "面向对象方法学的核心思想更接近下列哪一项？",
                "options": [
                    "A. 把数据和处理严格分离",
                    "B. 把数据及其相关操作封装为对象",
                    "C. 所有功能都写在一个主程序中",
                    "D. 先写代码再补模型",
                ],
                "answer": "B",
                "analysis": "面向对象方法学强调对象封装，把状态和行为统一到对象中组织系统。",
                "knowledge": ["面向对象方法学的要点", "面向对象的概念"],
                "keywords": ["面向对象", "封装", "对象"],
            },
            {
                "stem": "下列哪一项最能体现面向对象方法学的优点？",
                "options": [
                    "A. 更容易支持重用、扩展和维护",
                    "B. 一定会消除所有软件缺陷",
                    "C. 完全不需要需求分析",
                    "D. 不再需要测试",
                ],
                "answer": "A",
                "analysis": "面向对象方法学通过封装、继承、多态等机制，通常更利于复用、扩展和维护。",
                "knowledge": ["面向对象方法学的优点", "面向对象方法学引论"],
                "keywords": ["面向对象优点", "重用", "扩展", "维护"],
            },
            {
                "stem": "在面向对象概念中，类和对象的关系最准确的是哪一项？",
                "options": [
                    "A. 类是对象的一个属性",
                    "B. 对象是类的实例",
                    "C. 类和对象没有任何关系",
                    "D. 对象可以脱离类定义而存在于分析模型中",
                ],
                "answer": "B",
                "analysis": "类是对具有共同属性和行为对象的抽象，对象则是类的具体实例。",
                "knowledge": ["面向对象的概念", "确定类与对象"],
                "keywords": ["类", "对象", "实例"],
            },
            {
                "stem": "在面向对象建模中，用例图主要用于描述哪一项？",
                "options": [
                    "A. 类的内部代码结构",
                    "B. 用户与系统之间的交互功能",
                    "C. 数据库存储页布局",
                    "D. 编译优化过程",
                ],
                "answer": "B",
                "analysis": "用例图从外部用户视角描述系统提供的功能以及参与者和用例之间的关系。",
                "knowledge": ["用例图", "面向对象建模", "功能模型"],
                "keywords": ["用例图", "功能模型", "交互"],
            },
            {
                "stem": "动态模型主要关注下列哪一项？",
                "options": [
                    "A. 对象静态属性列表",
                    "B. 对象或系统随事件变化的行为",
                    "C. 代码缩进风格",
                    "D. 磁盘存储容量",
                ],
                "answer": "B",
                "analysis": "动态模型关注对象状态、事件和行为变化，描述系统的时间相关特征。",
                "knowledge": ["动 态 模 型", "状态转换图"],
                "keywords": ["动态模型", "状态", "事件", "行为"],
            },
        ],
    },
    7: {
        "title": "面向对象分析",
        "start_no": 11,
        "questions": [
            {
                "stem": "在面向对象分析中，用例图的主要用途是哪一项？",
                "options": [
                    "A. 描述用户可见的系统功能",
                    "B. 直接替代源代码实现",
                    "C. 只描述数据库表结构",
                    "D. 只用于性能调优",
                ],
                "answer": "A",
                "analysis": "用例图从用户视角刻画系统提供的服务，是面向对象分析的重要功能建模工具。",
                "knowledge": ["用例图", "功能模型", "面向对象建模"],
                "keywords": ["用例图", "功能模型", "面向对象分析"],
            },
            {
                "stem": "脚本在面向对象分析中的主要作用更接近下列哪一项？",
                "options": [
                    "A. 描述典型场景中的交互过程",
                    "B. 替代所有状态图",
                    "C. 直接生成数据库索引",
                    "D. 只统计项目工时",
                ],
                "answer": "A",
                "analysis": "脚本用于描述场景和事件序列，帮助分析系统交互过程并发现对象和职责。",
                "knowledge": ["编写脚本", "建立动态模型"],
                "keywords": ["脚本", "场景", "动态模型", "分析"],
            },
            {
                "stem": "状态图更适合在面向对象分析中表达下列哪一项？",
                "options": [
                    "A. 类之间的继承树",
                    "B. 对象生命周期中的状态变化",
                    "C. 团队分工表",
                    "D. 成本估算公式",
                ],
                "answer": "B",
                "analysis": "状态图主要描述对象在事件触发下如何从一个状态迁移到另一个状态。",
                "knowledge": ["画状态图", "动 态 模 型"],
                "keywords": ["状态图", "状态迁移", "动态模型"],
            },
            {
                "stem": "建立对象模型时，首先需要重点识别的是哪一项？",
                "options": [
                    "A. 关键类、对象及其关系",
                    "B. 编译器优化选项",
                    "C. 网络带宽限制",
                    "D. 磁盘碎片情况",
                ],
                "answer": "A",
                "analysis": "对象模型的核心是识别问题域中的关键类、对象、属性、关联和继承关系。",
                "knowledge": ["建立对象模型", "确定类与对象", "确定关联"],
                "keywords": ["对象模型", "类", "对象", "关联"],
            },
            {
                "stem": "功能模型在面向对象分析中的作用主要是哪一项？",
                "options": [
                    "A. 只保存界面配色信息",
                    "B. 补充说明系统需要完成的处理和输入输出",
                    "C. 替代对象模型和动态模型",
                    "D. 只用于编码规范检查",
                ],
                "answer": "B",
                "analysis": "功能模型强调系统处理过程，与对象模型和动态模型一起构成完整的分析视图。",
                "knowledge": ["功能模型", "建立功能模型", "面向对象分析"],
                "keywords": ["功能模型", "处理过程", "面向对象分析"],
            },
        ],
    },
    8: {
        "title": "面向对象设计",
        "start_no": 9,
        "questions": [
            {
                "stem": "面向对象设计准则的核心取向更接近下列哪一项？",
                "options": [
                    "A. 提高模块间耦合，减少封装",
                    "B. 保持高内聚、低耦合并支持重用",
                    "C. 尽量取消抽象和分层",
                    "D. 所有设计都只围绕数据库展开",
                ],
                "answer": "B",
                "analysis": "面向对象设计准则与结构化设计的优良结构原则一致，强调高内聚、低耦合、清晰职责和可重用性。",
                "knowledge": ["面向对象设计的准则", "模块独立", "启发规则"],
                "keywords": ["设计准则", "高内聚", "低耦合", "重用"],
            },
            {
                "stem": "软件重用能够带来的直接收益通常是哪一项？",
                "options": [
                    "A. 增加重复开发工作量",
                    "B. 降低开发成本并缩短开发周期",
                    "C. 使系统无法维护",
                    "D. 完全消除需求变化",
                ],
                "answer": "B",
                "analysis": "复用已有类构件可以减少重复编码和测试，从而降低成本并提高交付效率。",
                "knowledge": ["类构件", "软件重用的效益"],
                "keywords": ["软件重用", "类构件", "开发成本"],
            },
            {
                "stem": "设计人机交互子系统时，对用户分类的主要目的是什么？",
                "options": [
                    "A. 为不同类型用户提供更合适的交互方式",
                    "B. 只为了减少数据库字段数量",
                    "C. 只为了增加代码行数",
                    "D. 只为了删除帮助信息",
                ],
                "answer": "A",
                "analysis": "不同用户的任务、经验和使用频率不同，因此界面设计需要针对用户群体做适配。",
                "knowledge": ["设计人机交互子系统", "人机界面设计"],
                "keywords": ["人机交互", "用户分类", "界面设计"],
            },
            {
                "stem": "系统分解在面向对象设计中的主要意义是哪一项？",
                "options": [
                    "A. 把系统按责任划分为若干更易管理的部分",
                    "B. 只把代码文件随机拆分",
                    "C. 只用于生成流程图",
                    "D. 只在测试完成后进行",
                ],
                "answer": "A",
                "analysis": "系统分解有助于控制复杂度，把系统按职责划分为子系统或模块，便于设计和实现。",
                "knowledge": ["系 统 分 解", "面向对象设计"],
                "keywords": ["系统分解", "子系统", "复杂度控制"],
            },
            {
                "stem": "调整继承关系的主要目的通常是哪一项？",
                "options": [
                    "A. 让继承层次尽量更混乱",
                    "B. 让抽象更合理，减少重复并改善扩展性",
                    "C. 让所有类都直接继承同一个具体类",
                    "D. 只为减少类图节点数量",
                ],
                "answer": "B",
                "analysis": "继承关系应服务于抽象和重用，合理调整可以减少重复、提升可扩展性和模型一致性。",
                "knowledge": ["调整继承关系", "面向对象设计"],
                "keywords": ["继承关系", "抽象", "扩展性", "重用"],
            },
        ],
    },
    9: {
        "title": "面向对象实现",
        "start_no": 10,
        "questions": [
            {
                "stem": "选择面向对象语言时，下面哪一项通常属于重要考虑因素？",
                "options": [
                    "A. 语言对封装、继承、多态等机制的支持程度",
                    "B. 程序员最喜欢的键盘颜色",
                    "C. 办公室座位排列方式",
                    "D. 是否完全不需要编译或调试",
                ],
                "answer": "A",
                "analysis": "选择面向对象语言时需要关注其对核心 OO 机制、类型系统、工具链和运行效率的支持。",
                "knowledge": ["选择面向对象语言", "面向对象语言的技术特点"],
                "keywords": ["面向对象语言", "选择语言", "技术特点"],
            },
            {
                "stem": "面向对象语言的一个典型优点是下列哪一项？",
                "options": [
                    "A. 更容易表达对象抽象并支持代码重用",
                    "B. 一定能让程序没有任何缺陷",
                    "C. 一定比所有过程式语言运行更快",
                    "D. 完全不需要设计",
                ],
                "answer": "A",
                "analysis": "OO 语言与面向对象分析设计模型更贴近，通常更利于抽象、重用和维护。",
                "knowledge": ["面向对象语言的优点", "面向对象实现"],
                "keywords": ["面向对象语言", "优点", "重用", "抽象"],
            },
            {
                "stem": "下列哪一项最有助于提高软件的可重用性？",
                "options": [
                    "A. 把所有逻辑写死在单个类里",
                    "B. 设计可复用的类构件并保持清晰接口",
                    "C. 删除所有抽象层",
                    "D. 拒绝任何参数化设计",
                ],
                "answer": "B",
                "analysis": "高可重用性通常来自清晰职责、稳定接口、低耦合和可复用类构件。",
                "knowledge": ["提高可重用性", "类构件", "程序设计风格"],
                "keywords": ["可重用性", "类构件", "接口设计"],
            },
            {
                "stem": "下列哪一项更属于面向对象单元测试关注的重点？",
                "options": [
                    "A. 类的接口、状态变化和方法行为",
                    "B. 只检查编译器版本",
                    "C. 只检查网络带宽",
                    "D. 只检查 UI 配色",
                ],
                "answer": "A",
                "analysis": "面向对象单元测试以类为核心，关注对象状态、方法行为和类间协作接口。",
                "knowledge": ["面向对象的单元测试", "测试类的方法", "测试策略"],
                "keywords": ["单元测试", "类测试", "测试策略"],
            },
            {
                "stem": "提高可扩充性的设计做法更接近下列哪一项？",
                "options": [
                    "A. 通过清晰接口和抽象隔离变化点",
                    "B. 让所有模块共享同一份可随意修改的全局状态",
                    "C. 取消封装，直接暴露内部实现",
                    "D. 把所有新增需求写进主函数",
                ],
                "answer": "A",
                "analysis": "提高可扩充性的关键是隔离变化点、保持稳定接口并利用抽象降低修改影响面。",
                "knowledge": ["提高可扩充性", "提高可重用性"],
                "keywords": ["可扩充性", "抽象", "接口", "变化隔离"],
            },
        ],
    },
    10: {
        "title": "软件项目管理",
        "start_no": 13,
        "questions": [
            {
                "stem": "代码行技术主要用于下列哪一项？",
                "options": [
                    "A. 用代码规模近似估算开发工作量",
                    "B. 描述状态迁移",
                    "C. 设计测试边界值",
                    "D. 替代配置管理",
                ],
                "answer": "A",
                "analysis": "代码行技术把源程序规模作为估算依据，常用于工作量、成本和进度的粗略估计。",
                "knowledge": ["代码行技术", "工作量估算"],
                "keywords": ["代码行技术", "工作量估算", "项目管理"],
            },
            {
                "stem": "功能点技术相较于代码行技术的一个重要特点是下列哪一项？",
                "options": [
                    "A. 更依赖具体编程语言语法",
                    "B. 更从用户可见功能角度估算系统规模",
                    "C. 只能在编码完成后使用",
                    "D. 不能用于成本估算",
                ],
                "answer": "B",
                "analysis": "功能点技术从输入、输出、查询、内部逻辑文件等用户功能视角估算规模，语言相关性较弱。",
                "knowledge": ["功能点技术", "工作量估算"],
                "keywords": ["功能点技术", "规模估算", "用户功能"],
            },
            {
                "stem": "关键路径是指下列哪一项？",
                "options": [
                    "A. 所有任务中最便宜的一组任务",
                    "B. 决定项目最短工期且没有机动时间的一条任务路径",
                    "C. 资源投入最多的一条路径",
                    "D. 只包含测试任务的路径",
                ],
                "answer": "B",
                "analysis": "关键路径决定项目总工期，路径上的任务若延期会直接推迟项目完成时间。",
                "knowledge": ["关键路径", "工程网络", "估算工程进度"],
                "keywords": ["关键路径", "工程网络", "项目进度"],
            },
            {
                "stem": "配置管理的主要目标更接近下列哪一项？",
                "options": [
                    "A. 阻止任何需求变化发生",
                    "B. 对配置项及其变更进行标识、控制和追踪",
                    "C. 只记录员工考勤",
                    "D. 只维护服务器硬件",
                ],
                "answer": "B",
                "analysis": "配置管理的重点是识别配置项、控制变更、保持一致性并支持审计追踪。",
                "knowledge": ["软件配置管理", "软件配置", "软件配置管理过程"],
                "keywords": ["配置管理", "配置项", "变更控制"],
            },
            {
                "stem": "CMM 将能力成熟度划分为多个等级，主要是为了哪一项？",
                "options": [
                    "A. 让组织一次性跳过过程改进",
                    "B. 为过程改进提供循序渐进的评估和提升路径",
                    "C. 只评价程序员个人编码速度",
                    "D. 替代所有质量保证活动",
                ],
                "answer": "B",
                "analysis": "CMM 的核心是通过分级刻画过程成熟度，帮助组织识别当前水平并持续改进过程能力。",
                "knowledge": ["能力成熟度模型", "质 量 保 证"],
                "keywords": ["CMM", "能力成熟度", "过程改进", "质量保证"],
            },
        ],
    },
}


def stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:12]}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    target = path.with_name(f"{path.name}.bak_{stamp}")
    for _ in range(3):
        try:
            shutil.copy2(path, target)
            return
        except PermissionError:
            time.sleep(0.5)
    print(f"skip backup for locked file: {path}")


def build_knowledge_lookup() -> dict:
    payload = load_json(KNOWLEDGE_PATH)
    items = payload.get("knowledge_points", [])
    return {str(item.get("knowledge_id")): item for item in items}


def build_title_lookup(knowledge_lookup: dict) -> dict:
    result = {}
    for item in knowledge_lookup.values():
        title = str(item.get("title") or "").strip()
        if title and title not in result:
            result[title] = item
        normalized = normalize_text(title)
        if normalized and normalized not in result:
            result[normalized] = item
    return result


def normalize_text(value: str) -> str:
    return re.sub(r"[\s/,_\-，。；：、“”‘’（）()【】\[\]]+", "", str(value or "")).lower()


def knowledge_ref(item: dict, chapter_no: int, score: int = 100) -> dict:
    learning_location = item.get("learning_location") or {}
    return {
        "knowledge_id": item.get("knowledge_id"),
        "node_id": item.get("knowledge_id"),
        "title": item.get("title"),
        "section_path": item.get("section_path") or [],
        "learning_location": learning_location,
        "pages": item.get("pages") or learning_location.get("pages") or [],
        "knowledge_type": item.get("knowledge_type") or "main_knowledge",
        "score": score,
        "confidence": 0.98,
        "match_reasons": [f"manual_chapter{chapter_no}_choice_mapping"],
    }


def build_question(chapter_no: int, item: dict, title_lookup: dict) -> dict:
    chapter_title = CHAPTERS[chapter_no]["title"]
    question_no = item["question_no"]
    stem = f"{question_no}. {item['stem'].strip()}"
    answer = item["answer"].strip()
    option_text = next(option for option in item["options"] if option.startswith(f"{answer}."))
    reference_answer = f"{answer}：{option_text[3:].strip()}\n{item['analysis']}"
    refs = []
    for index, title in enumerate(item["knowledge"]):
        candidate = title_lookup.get(title) or title_lookup.get(normalize_text(title))
        if not candidate:
            normalized = normalize_text(title)
            for key, value in title_lookup.items():
                if not isinstance(key, str):
                    continue
                compact = normalize_text(key)
                if not compact:
                    continue
                if normalized in compact or compact in normalized:
                    candidate = value
                    break
        if not candidate:
            raise KeyError(f"knowledge title not found: chapter {chapter_no} / {title}")
        refs.append(knowledge_ref(candidate, chapter_no, max(88, 100 - index * 4)))
    titles = [ref["title"] for ref in refs]
    question_id = stable_id("question", f"chapter{chapter_no}_choice:{question_no}:{stem}")
    answer_id = stable_id("answer", f"chapter{chapter_no}_choice:{question_no}:{answer}:{item['analysis']}")
    link_id = stable_id("qa_link", f"{question_id}:{answer_id}")
    section_path = ["软件工程", chapter_title, f"第 {chapter_no} 章 {chapter_title}", "选择题"]
    learning_location = {
        "unit": "软件工程",
        "chapter": chapter_title,
        "section": f"第 {chapter_no} 章 {chapter_title}",
        "subsection": "选择题",
        "path": section_path,
        "path_text": " / ".join(section_path),
        "pages": [],
    }
    return {
        "question_id": question_id,
        "course": "软件工程",
        "source_file": rf"C:\Users\ASUS\Desktop\新建文件夹\timu\{chapter_no}\choice_generated.txt",
        "section_title": f"第 {chapter_no} 章 {chapter_title} 选择题",
        "section_path": section_path,
        "page": None,
        "pages": [],
        "question_type": "single_choice",
        "difficulty_level": "基础",
        "stem": stem,
        "options": item["options"],
        "content": stem + "\n" + "\n".join(item["options"]),
        "answer": answer,
        "reference_answer": reference_answer,
        "has_answer": True,
        "can_auto_grade": True,
        "analysis": item["analysis"],
        "images": [],
        "question_images": [],
        "has_images": False,
        "has_question_images": False,
        "answer_images": [],
        "has_answer_images": False,
        "image_count": 0,
        "answer_image_count": 0,
        "related_knowledge": refs,
        "related_knowledge_ids": [ref["knowledge_id"] for ref in refs],
        "related_knowledge_node_ids": [ref["node_id"] for ref in refs],
        "related_knowledge_titles": titles,
        "primary_knowledge_titles": titles[:1],
        "prerequisite_knowledge_titles": [],
        "confidence": 0.98,
        "requires_image": False,
        "metadata": {
            "source_question_file": rf"C:\Users\ASUS\Desktop\新建文件夹\timu\{chapter_no}\choice_generated.txt",
            "source_answer_file": rf"C:\Users\ASUS\Desktop\新建文件夹\timu\{chapter_no}\choice_generated_answer.txt",
            "cleaning_method": "manual_generated_choice_questions",
            "replacement_scope": f"append_chapter{chapter_no}_choice_questions",
            "chapter": f"第 {chapter_no} 章 {chapter_title}",
            "chapter_no": chapter_no,
            "question_no": question_no,
            "question_chapter_key": f"chapter_{chapter_no}",
            "answer_id": answer_id,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "question_chapter_key": f"chapter_{chapter_no}",
        "question_no_raw": str(question_no),
        "parent_question_id": None,
        "parent_stem": "",
        "is_complete_question": True,
        "knowledge_points": titles,
        "related_knowledge_match_score": 100,
        "question_no": question_no,
        "question_no_int": question_no,
        "sub_question_no": "",
        "answer_link_ids": [link_id],
        "answer_ids": [answer_id],
        "has_answer_link": True,
        "answer_link_confidence": 1.0,
        "answer_link_method": "manual_generated_choice_answer",
        "answer_links": [
            {
                "answer_id": answer_id,
                "confidence": 1.0,
                "method": "manual_generated_choice_answer",
                "answer_no": question_no,
                "question_chapter_key": f"chapter_{chapter_no}",
            }
        ],
        "learning_location": learning_location,
        "content_preview": stem[:180],
        "knowledge_relations": [],
        "answer_pages": [],
        "_v21_full_reference_answer": reference_answer,
        "keywords": item["keywords"],
    }


def sort_key(question: dict) -> tuple[int, int, str]:
    key = str(question.get("question_chapter_key") or "")
    chapter = 99
    if key.startswith("chapter_"):
        try:
            chapter = int(key.split("_", 1)[1])
        except ValueError:
            chapter = 99
    return chapter, int(question.get("question_no_int") or question.get("question_no") or 0), str(question.get("question_id") or "")


def update_payload(path: Path, chapter_questions: dict[int, list[dict]]) -> None:
    payload = load_json(path)
    replace_scopes = {f"append_chapter{chapter_no}_choice_questions" for chapter_no in chapter_questions}
    replace_ids = {question["question_id"] for questions in chapter_questions.values() for question in questions}
    kept = []
    for question in payload.get("questions", []):
        metadata = question.get("metadata") or {}
        if metadata.get("replacement_scope") in replace_scopes:
            continue
        if str(question.get("question_id") or "") in replace_ids:
            continue
        kept.append(question)
    merged = kept + [question for questions in chapter_questions.values() for question in questions]
    payload["questions"] = sorted(merged, key=sort_key)

    stats = dict(payload.get("stats") or {})
    stats["question_count"] = len(payload["questions"])
    stats["answered_question_count"] = sum(1 for question in payload["questions"] if question.get("has_answer"))
    stats["auto_gradable_question_count"] = sum(1 for question in payload["questions"] if question.get("can_auto_grade"))
    stats["answer_linked_question_count"] = sum(1 for question in payload["questions"] if question.get("has_answer_link"))
    for chapter_no, questions in chapter_questions.items():
        stats[f"chapter{chapter_no}_choice_question_count"] = len(questions)
        stats[f"chapter{chapter_no}_question_count"] = sum(
            1
            for question in payload["questions"]
            if question.get("question_chapter_key") == f"chapter_{chapter_no}"
        )
    if path == STUDENT_KB_PATH:
        stats["questions"] = stats["answer_linked_question_count"]
    payload["stats"] = stats

    replacement = dict(payload.get("question_replacement") or {})
    for chapter_no, questions in chapter_questions.items():
        replacement[f"chapter{chapter_no}_choice_questions"] = {
            "count": len(questions),
            "question_nos": [question["question_no"] for question in questions],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "method": "manual_generated_choice_questions",
        }
    payload["question_replacement"] = replacement
    backup(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    knowledge_lookup = build_knowledge_lookup()
    title_lookup = build_title_lookup(knowledge_lookup)
    chapter_questions = {}
    for chapter_no, config in CHAPTERS.items():
        questions = []
        for index, item in enumerate(config["questions"], start=0):
            questions.append(
                build_question(
                    chapter_no,
                    {**item, "question_no": config["start_no"] + index},
                    title_lookup,
                )
            )
        chapter_questions[chapter_no] = questions

    for path in (QUESTION_PATH, QUESTION_BANK_PATH, STUDENT_KB_PATH):
        update_payload(path, chapter_questions)

    total = sum(len(questions) for questions in chapter_questions.values())
    print(f"inserted {total} choice questions for chapters 2-10")


if __name__ == "__main__":
    main()
