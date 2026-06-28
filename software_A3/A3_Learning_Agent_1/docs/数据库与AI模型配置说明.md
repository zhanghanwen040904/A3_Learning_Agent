# 数据库与真实 AI 模型配置说明

## 1. 数据库在项目中的应用

本项目使用 MySQL 作为业务数据库，不是只做页面演示。数据库贯穿登录、画像、资源、路径、评估和学习闭环。

## 2. 数据库表说明

| 表名 | 应用位置 | 说明 |
| --- | --- | --- |
| user | 登录注册 | 保存用户账号和密码哈希 |
| student_profile | 对话式画像 | 保存六维学习画像，评估后会动态更新 |
| study_resource | 学习资源 | 保存多智能体生成的讲解文档、题库、阅读、思维导图、代码案例、视频任务 |
| study_path | 学习路径 | 保存个性化学习路径 |
| quiz_result | 学习评估 | 保存题目、答案、分数和反馈 |
| mastery_record | 学习评估闭环 | 保存知识点掌握度，用于后续路径和画像更新 |
| learning_event | 学习行为追踪 | 保存练习、答疑、资源访问等学习行为 |
| resource_feedback | 资源反馈 | 保存学生对资源的评分和评价 |

## 3. 数据流说明

### 3.1 登录注册

1. 前端提交用户名和密码；
2. 后端写入 `user` 表；
3. 登录成功后返回 JWT；
4. 后续接口通过 JWT 识别当前用户。

### 3.2 对话式画像

1. 学生输入自然语言学习情况；
2. ProfileAgent 解析画像；
3. 后端写入或更新 `student_profile` 表。

### 3.3 资源生成

1. 后端从 `student_profile` 读取画像；
2. 多智能体生成资源；
3. 资源写入 `study_resource` 表；
4. 前端再次进入页面时从数据库读取最新资源。

### 3.4 学习路径

1. PathAgent 基于画像和知识库生成路径；
2. 后端写入 `study_path` 表；
3. 前端从数据库加载历史路径。

### 3.5 学习评估闭环

1. 学生提交练习答案；
2. EvaluatorAgent 自动评分；
3. 写入 `quiz_result`；
4. 更新 `mastery_record`；
5. 写入 `learning_event`；
6. 根据掌握度更新 `student_profile`。

## 4. 如何在界面查看数据库是否连接

启动项目后进入：

```text
系统状态
```

可以看到：

- MySQL 是否已连接；
- 当前数据库名；
- MySQL 版本；
- 各业务表数据量；
- 每张表在项目中的用途。

## 5. 真实 AI 模型接入说明

后端 AI 调用集中在：

```text
backend/ai/spark_api.py
```

包含：

- `spark_chat()`：调用讯飞 Spark X；
- `see_dance_generate()`：调用讯飞 SeeDance；
- `content_audit()`：调用讯飞内容审核。

## 6. 为什么现在看起来像没有连接真实模型

如果 `backend/.env` 中：

```env
MOCK_AI=true
```

或者没有填写真实讯飞密钥，系统会自动进入模拟演示模式。模拟模式用于没有 API 密钥时保证比赛演示流程稳定，但这不是最终真实模型模式。

## 7. 如何启用真实讯飞星火模型

修改 `backend/.env`：

```env
MOCK_AI=false
XFYUN_APP_ID=你的讯飞APP_ID
XFYUN_API_KEY=你的讯飞APIKey
XFYUN_API_SECRET=你的讯飞APISecret
XFYUN_SPARK_URL=wss://spark-api.xf-yun.com/x2
XFYUN_SPARK_DOMAIN=spark-x
```

然后重启后端：

```bash
cd backend
python app.py
```

进入前端：

```text
系统状态 → AI 连通性测试
```

如果返回真实模型结果，说明星火模型已连接成功。

## 8. SeeDance 与内容审核配置

如需启用 SeeDance 和内容审核，继续配置：

```env
SEEDANCE_API_KEY=你的SeeDance密钥
SEEDANCE_API_URL=你的SeeDance接口地址
CONTENT_AUDIT_API_KEY=你的内容审核密钥
CONTENT_AUDIT_API_URL=你的内容审核接口地址
```

如果未配置，系统会在“系统状态”页面显示未配置。

## 9. 评审展示建议

演示时建议打开“系统状态”页面，说明：

1. 数据库已经连接；
2. 每张表都有明确业务用途；
3. 当前 AI 是模拟模式还是真实讯飞模型模式；
4. 如果已填真实密钥，可以现场点击 AI 连通性测试。
