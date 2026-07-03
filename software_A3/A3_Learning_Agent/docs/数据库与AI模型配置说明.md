# 数据库与 AI 模型配置说明

## 数据库

项目默认使用 MySQL，核心配置如下：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=a3_learning_agent
```

## AI 模型

当前项目主模型统一使用百炼兼容接口：

```env
AI_PROVIDER=bailian
BAILIAN_API_KEY=你的百炼 API Key
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
BAILIAN_MODEL=qwen-plus
```

## 其他可选能力

- `SEEDANCE_API_KEY / SEEDANCE_API_URL`：视频生成能力
- `CONTENT_AUDIT_API_KEY / CONTENT_AUDIT_API_URL`：内容审核能力

## 演示说明

若未配置真实模型，可使用：

```env
MOCK_AI=true
```

用于本地调试与界面演示。
