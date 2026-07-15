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

当前项目主模型统一使用讯飞星火 Spark Ultra-32K HTTP 兼容接口：

```env
AI_PROVIDER=spark
AI_MAX_INPUT_CHARS=24000
AI_MAX_TOKENS=4096
SPARK_APIPASSWORD=你的讯飞 APIPassword
SPARK_BASE_URL=https://spark-api-open.xf-yun.com/v1/chat/completions
SPARK_MODEL=4.0Ultra
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
