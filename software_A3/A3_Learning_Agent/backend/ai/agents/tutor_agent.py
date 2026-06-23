from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.spark_api import spark_chat


class TutorAgent:
    def __init__(self):
        self.role = "多模态软件工程答疑老师"
        self.goal = "严格基于课程知识库回答学生问题，并输出结构清晰、层级固定、适合配图展示的答疑内容。"

    def answer(self, question: str) -> dict:
        evidence_items = retrieve_knowledge_items(question, top_k=3)
        evidence = retrieve_knowledge(question, top_k=3)
        prompt = f"""
你是软件工程课程的多模态答疑老师。请严格基于教材与知识库回答，不要编造。

输出必须严格按以下 4 个部分组织，标题顺序不能变化，不能缺少任何一部分：
1. `## 一、直接回答`
2. `## 二、图解说明`
3. `## 三、易错点`
4. `## 四、自测题`

写作规则：
- 全文使用简洁、流畅的 Markdown。
- 不要使用代码块包裹全文。
- 第一部分先给一句结论，再给 2-4 句解释。
- 第二部分必须先写一句“核心观点”，且这句话要放在最上层，明确说明这道题的主线关系。
- 第二部分不要写长篇论述，优先用“核心观点 + 分步骤/对比关系 + 关键词”风格。
- 第三部分写 2-4 条最容易混淆的点，每条都要带纠正说明。
- 第四部分写 1-3 道简短自测题，题型可以是判断、单选或简答。
- 如果证据不足，要明确说明“教材中暂未找到足够依据”，不要虚构。

问题：{question}

课程知识库证据：{evidence}
""".strip()
        answer = spark_chat(prompt)
        return {"answer": answer, "evidence": evidence, "sources": evidence_items}
