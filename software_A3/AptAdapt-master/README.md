# AptAdapt

基于大模型的《计算机组成原理》个性化资源生成与学习多智能体系统

> 中国软件杯 A3 赛题 — 基于大模型的个性化资源生成与学习多智能体系统开发

## 项目简介

AptAdapt 面向高校《计算机组成原理》课程，构建一个基于大模型和多智能体协同的个性化学习平台。系统通过自然语言对话理解学生基础、学习目标和薄弱点，自动生成学习画像；结合课程知识库、多智能体资源生成与路径规划能力，为学生提供个性化讲解文档、知识点思维导图、练习题、代码示例、视频脚本和动态学习路径。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端框架 | FastAPI + JWT 认证 |
| 前端框架 | Vue3 + Element Plus |
| 大模型 | 讯飞星火 Chat API + Embedding API |
| 多智能体编排 | LangGraph |
| 向量知识库 | Chroma |
| 数据库 | SQLite |
| 前端可视化 | Mermaid / jsMind / ECharts / markdown-it |
| 流式输出 | SSE (Server-Sent Events) |

## 功能特性

- **学生画像生成**：通过对话自动抽取 6+ 维度画像（专业背景、知识基础、学习目标、薄弱点、学习偏好、学习节奏）
- **课程知识库检索**：覆盖 20-30 个《计算机组成原理》核心知识点，基于 Chroma 向量检索
- **多智能体协同**：Supervisor + 5 个 Worker Agent + Reviewer 的多智能体架构
- **五类资源生成**：讲解文档、思维导图、练习题、代码案例、视频脚本
- **个性化学习路径**：基于知识点 DAG 和学生薄弱点自动规划学习顺序
- **Reviewer 审核**：内容事实性校验，引用知识库来源，降低幻觉
- **流式交互体验**：SSE 实时展示生成过程和 Agent 状态

## 多智能体架构

| Agent | 职责 | 输出 |
| --- | --- | --- |
| Supervisor Agent | 任务识别、流程编排、状态流转 | 调用计划 |
| Profile Agent | 从对话中抽取和更新学生画像 | 学生画像 JSON |
| Doc Agent | 生成个性化讲解文档 | Markdown 文档 |
| MindMap Agent | 生成知识点思维导图 | Mermaid / jsMind |
| Quiz Agent | 生成选择题、判断题、简答题和解析 | 题目 JSON |
| Code Agent | 生成 Verilog / 汇编 / 伪代码示例 | 代码块与解释 |
| VideoScript Agent | 生成短视频讲解脚本和分镜 | 视频脚本 |
| Reviewer Agent | 校验事实性、安全性、完整性 | 审核结果与修改建议 |
| Planner Agent | 根据知识点 DAG 生成学习路径 | 路径节点列表 |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 讯飞星火 API Key

### 后端启动

```bash
pip install -r requirements.txt
cd app
uvicorn main:app --reload
```

访问 http://localhost:8000/docs 查看 Swagger 接口文档。

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 知识库初始化（规划中）

将《计算机组成原理》教材/讲义文本分知识点切分后，通过讯飞 Embedding API 生成向量并存入 Chroma。

## 项目结构

```
AptAdapt/
├── app/                          # FastAPI 后端
│   ├── main.py                   # 入口，路由注册，数据库初始化
│   ├── config.py                 # 讯飞 API 密钥、JWT、数据库配置
│   ├── database.py               # SQLAlchemy 引擎与会话管理
│   ├── models.py                 # ORM 模型 (User)
│   ├── schemas.py                # Pydantic 请求/响应模型
│   ├── llm_client.py             # 讯飞星火 Chat API WebSocket 客户端
│   ├── routers/
│   │   ├── auth.py               # 注册/登录接口
│   │   └── chat.py               # 对话接口
│   └── utils/
│       └── jwt_handler.py        # JWT Token 生成与验证
├── frontend/                     # Vue3 前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js               # Vue3 入口
│       ├── App.vue               # 根组件
│       ├── router/index.js       # 路由配置
│       ├── api/                  # 后端接口封装
│       │   ├── index.js          # axios 实例
│       │   ├── auth.js           # 认证接口
│       │   ├── chat.js           # 对话/资源接口
│       │   └── sse.js            # SSE 流式连接
│       ├── stores/user.js        # Pinia 用户状态
│       ├── views/
│       │   ├── LoginView.vue     # 登录注册页
│       │   └── MainLayout.vue    # 主工作台（三栏布局）
│       └── components/
│           ├── ChatPanel.vue      # 对话区 + 流式输出
│           ├── PathTree.vue       # 学习路径树
│           ├── ResourcePanel.vue  # 资源卡片列表
│           ├── MarkdownViewer.vue # Markdown 渲染
│           ├── MindMapViewer.vue  # Mermaid 思维导图
│           ├── QuizCard.vue       # 练习题作答
│           ├── CodeBlock.vue      # 代码高亮
│           ├── ProfileCard.vue    # 学生画像卡片
│           ├── EvaluationPanel.vue# ECharts 评估图表
│           └── AgentStatusBar.vue # 智能体运行状态
├── agents/                       # LangGraph 多智能体编排
│   ├── state.py                  # 全局状态定义
│   ├── supervisor.py             # Supervisor 路由编排
│   ├── reviewer.py               # Reviewer 审核
│   ├── planner.py                # 学习路径规划
│   ├── workers/
│   │   ├── profile_agent.py      # 画像抽取
│   │   ├── doc_agent.py          # 讲解文档生成
│   │   ├── mindmap_agent.py      # 思维导图生成
│   │   ├── quiz_agent.py         # 练习题生成
│   │   ├── code_agent.py         # 代码案例生成
│   │   └── video_script_agent.py # 视频脚本生成
│   ├── prompts/                  # Prompt 模板
│   │   ├── supervisor_prompt.txt
│   │   ├── doc_prompt.txt
│   │   ├── quiz_prompt.txt
│   │   ├── code_prompt.txt
│   │   ├── reviewer_prompt.txt
│   │   └── planner_prompt.txt
│   └── dag/
│       └── knowledge_dag.json    # 知识点 DAG 先修关系
├── knowledge_base/               # 课程知识库
│   └── computer_organization/
│       └── chunks.json           # 知识片段数据
├── docs/                         # 项目文档
│   ├── request.txt               # 赛题要求
│   ├── 项目方案与技术路线.md
│   ├── 模块拆解与实施计划.md
│   └── 需求分析文档.md
├── requirements.txt
└── README.md
```

## 核心接口

### 已实现

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 服务健康检查 |
| `/auth/register` | POST | 用户注册（bcrypt 加密） |
| `/auth/login` | POST | 用户登录，返回 JWT |
| `/chat/send` | POST | 发送消息，调用星火大模型 |

### 规划中

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/profile/get` | GET | 获取学生画像 |
| `/profile/update` | POST | 更新学生画像 |
| `/resource/generate` | POST | 按知识点生成多类资源 |
| `/path/get` | GET | 获取个性化学习路径 |
| `/quiz/submit` | POST | 提交练习题答案 |
| `/evaluation/get` | GET | 获取学习效果评估 |

## 团队

| 成员 | 角色 | 职责 |
| --- | --- | --- |
| 赵嘉诚 | 组长 / 多智能体 | LangGraph、Agent 编排、Prompt 模板、路径规划、测试 |
| 胡博涵 | 后端 | FastAPI、JWT、讯飞 API、Chroma 知识库、项目协调 |
| 徐英博 | 前端 / 演示 | Vue3、可视化组件、演示视频、PPT |

## 开发周期

20 天（3 周），分三阶段并行推进：

- 第 1 周：基础搭建与核心模块开发
- 第 2 周：联调对接与优化
- 第 3 周：演示材料与提交

## 许可证

本项目为中国软件杯参赛作品。
