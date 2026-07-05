# MY 目录语义切片流程

本目录把教材处理拆成两步，暂时不写入 MySQL。

## 1. PDF 转 JSON

```powershell
python .\MY\pdf_to_json.py --pdf "E:\教材\软件工程.pdf" --course "软件工程"
```

默认会在 PDF 同目录生成：

- `软件工程_pdf.json`

内容包括章节树、段落、规则切片预览。

## 2. 语义切片与知识树生成

先设置 API Key，不要写进代码：

```powershell
$env:LLM_API_KEY="你的APIKey"
```

调用 Qwen3.6-35B-A3B：

```powershell
python .\MY\semantic_slice_tree.py --input-json "E:\教材\软件工程_pdf.json" `
  --llm-base-url "https://maas-api.cn-huabei-1.xf-yun.com/v2" `
  --llm-model "Qwen3.6-35B-A3B" `
  --use-llm-boundaries `
  --generate-relations
```

默认在同目录生成：

- `软件工程_semantic.json`：语义切片结果
- `软件工程_knowledge_tree.json`：知识树节点与关系
- `软件工程_knowledge_tree.mmd`：Mermaid 思维导图预览

## 清洗与合并

`semantic_slice_tree.py` 默认会执行三类优化：

- 过滤非知识点：目录、课堂讨论、课堂练习、作业、学以致用、案例标题、小结标题、残缺流程图文字。
- 合并重复知识点：例如多个“快速原型模型”“软件过程”会合并为一个知识点，并保留来源页码。
- 规则关系兜底：如果大模型关系生成失败或关系为空，会按教材出现顺序补充 `next/prerequisite` 边，避免图谱完全无连接。

如果需要关闭这些默认优化：

```powershell
--no-filter-non-knowledge
--no-merge-duplicates
--no-rule-relation-fallback
```

## 建议

- 首次测试可以加 `--max-llm-chunks 5`，确认 API 调用正常后再跑完整教材。
- 如果只想离线生成规则切片和树，第二步不要加 `--use-llm-boundaries` 和 `--generate-relations`。
- 第二步也兼容旧的 `rule_chunks.json`，它会自动读取其中的 `knowledge_chunks`。
- 如果接口提示不支持 `response_format`，在第二步命令末尾追加 `--disable-response-format`。
- 截图里的 Key 已经暴露在聊天中，建议在平台重新生成或轮换密钥。
