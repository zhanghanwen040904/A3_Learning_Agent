from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class TutorAgent:
    def __init__(self):
        self.role = "多模态智能辅导老师"
        self.goal = "严格基于软件工程课程知识库回答学生问题，并输出适合直接出图的知识文案。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["retrieve_knowledge", "spark_chat", "see_dance_generate"],
            input_schema="学生问题",
            output_schema="Markdown答疑 + 课程来源",
        )

    def answer(self, question: str) -> dict:
        evidence_items = retrieve_knowledge_items(question, top_k=3)
        evidence = retrieve_knowledge(question, top_k=3)
        prompt = f"""
你是软件工程课程智能辅导老师。请严格基于教材原文回答学生问题，语言要简洁、准确、适合大学生复习。

输出格式必须使用普通 Markdown，禁止使用代码围栏，禁止输出 ASCII 图，禁止输出 Mermaid 源码，禁止输出 JSON。
请按下面四个一级标题输出，标题文字必须完全一致：

## 一、直接回答
用 2 到 4 段说明核心区别或核心结论。每段只讲一个重点，语言平实、直接、不要堆术语。

## 二、图解说明
这一节必须写成“可直接喂给出图模型”的知识图文案，不是说明文。要求如下：
1. 先给出一句图解主旨，概括这张图到底想展示什么。
2. 接着给出“画面布局”，必须包含：中心主题、左侧内容、右侧内容、底部总结、箭头方向、强调色。
3. 然后给出“图中节点”，必须拆成三组：
   - 核心节点：至少 10 个，每个 2 到 8 个字，只写短词，不写长句。
   - 关系节点：至少 5 条，每条用“节点A -> 节点B”或“节点A 关联 节点B”。
   - 视觉标注：至少 3 条，说明哪个地方是主标题、哪个地方是分区、哪个地方要突出显示。
4. 节点内容必须是知识点，不要只写“这是一个图”“这里很重要”这类空话。
5. 如果问题适合对比，要明确写出“左边是什么、右边是什么、差异点是什么”。
6. 文字必须适合视觉生成模型理解，避免长句、避免抽象空话、避免代码语言。

## 三、易错点
列出 3 个常见误区，每个误区用“误区：...；纠正：...”的格式，尽量贴近学生会画错、看错、记错的地方。

## 四、自测题
给出 2 道题，包含题目、答案和简短解析，题目尽量短，解析尽量准确。

如果教材证据不足，请明确说明“当前知识库依据不足”，不要编造页码、图片或事实。

学生问题：
{question}

教材原文：
{evidence}
""".strip()
        return {"answer": spark_chat(prompt), "evidence": evidence, "sources": evidence_items}
