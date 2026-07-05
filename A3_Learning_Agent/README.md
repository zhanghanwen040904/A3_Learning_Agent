# A3 Learning Agent

面向“软件杯”赛题的多智能体学习辅助系统。

当前版本已经统一切换到“阿里云百炼 / 通义千问”作为主大模型入口，后端保留课程知识库、学习画像、学习路径、学习评估与对话答疑等核心能力。

## 项目概览

- 前端：Vue 3 + Vite + Element Plus
- 后端：Flask + PyMySQL
- 检索：RAG 课程知识库 + 关键词降级检索
- 大模型：阿里云百炼兼容接口
- 画像机制：对话过程中自动抽取并持续更新学生画像

## 当前主要能力

- 对话式学习辅助：学生直接提问，系统结合上下文与知识库回答
- 自动画像更新：每轮对话后静默补充学生画像
- 学习路径生成：根据画像和课程内容生成阶段化学习建议
- 学习评估：基于题库进行诊断、评分和薄弱点识别
- 多资源生成：支持文档、练习、阅读材料、思维导图、代码案例、视频脚本等资源形态

## 目录结构

```text
A3_Learning_Agent/
├─ backend/                  # Flask 后端
│  ├─ ai/                    # LLM、智能体与资源生成逻辑
│  ├─ api/                   # REST API
│  ├─ db/                    # 数据库连接与表结构
│  └─ requirements.txt
├─ frontend/                 # Vue 前端
│  └─ src/
├─ rag_data/                 # 课程知识库与检索数据
├─ docs/                     # 项目文档
└─ README.md
```

## 启动方式

后端：

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
python app.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:5173
```

## 环境变量说明

当前主模型使用百炼兼容接口，核心变量如下：

```env
AI_PROVIDER=bailian
BAILIAN_API_KEY=你的百炼 API Key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
BAILIAN_MODEL=qwen-plus
```

如果只做本地演示，也可以启用：

```env
MOCK_AI=true
```

## 说明

- `frontend/dist/` 属于前端构建产物，不建议作为长期源码的一部分保留
- `.env`、数据库账号密码、真实 API Key 不要提交到 GitHub
- 如知识库尚未建立，请先进入“知识库管理”页面执行重建
