from .resource_base import StructuredResourceAgent


class MindMapAgent(StructuredResourceAgent):
    resource_type = "mindmap"
    role = "软件工程知识导图可视化设计师"
    goal = "把本地知识树关系转化为详细、结构化、白蓝风格的图形化知识导图"
    default_title = "软件工程知识导图"
    output_format = "mermaid"
    requirements = """
content 必须是合法 Mermaid flowchart 源码，以 flowchart LR 开头，不要使用 mindmap，不要包含 ``` 代码围栏。

你要生成的是“知识导图”，不是知识点清单。必须体现：
1. 分组：使用 subgraph 把内容分成 5-7 个模块。
2. 关系：用箭头表示先修、流程、产物、测试、反馈、易错点之间的关系。
3. 层次：每个模块 3-5 个节点，必要时可以有少量二级关系。
4. 详细：总节点数建议 28-45 个，不能只输出概览。
5. 主题：中心节点必须具体，例如“瀑布模型知识导图”“需求分析知识导图”，不要写“知识树”。
6. 视觉：节点文字短，每个节点不超过 16 个汉字；前端会使用白蓝色调渲染。
7. 图片：如果 images 非空，必须有“教材配图”模块，包含 2-4 个图片节点，节点文字保留图片路径。
8. 禁止输出 chunk_id、score、retrieval_mode、JSON 字段名。

推荐模块：
- 概念定位
- 学习前提
- 流程步骤
- 关键产物
- 测试与验证
- 优缺点/适用场景
- 易错点与实践任务
- 教材配图

示例格式：
flowchart LR
  A((瀑布模型知识导图))

  subgraph M1[概念定位]
    A --> B1[线性生命周期]
    B1 --> B2[阶段顺序]
    B1 --> B3[文档驱动]
  end

  subgraph M2[流程步骤]
    C1[需求分析] --> C2[总体设计]
    C2 --> C3[详细设计]
    C3 --> C4[编码实现]
    C4 --> C5[测试交付]
  end

  subgraph M3[关键产物]
    C1 --> D1[需求规格]
    C2 --> D2[设计文档]
    C5 --> D3[测试报告]
  end

  subgraph M4[测试与反馈]
    C4 --> E1[单元测试]
    E1 --> E2[集成测试]
    E2 --> E3[系统测试]
    E3 --> E4[验收测试]
  end

  subgraph M5[优缺点]
    F1[管理清晰]
    F2[变更困难]
    F3[反馈滞后]
  end

  subgraph M6[教材配图]
    P1[配图：瀑布模型示意图 E:\\...\\page_033_img_02.jpeg]
  end

  A --> B1
  A --> C1
  A --> F1
  C5 --> E1
  F2 -.风险.-> E3
""".strip()
