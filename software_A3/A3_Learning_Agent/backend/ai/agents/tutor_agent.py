import json

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.langchain_adapter import SparkLLM
from ai.rag import retrieve_knowledge, retrieve_knowledge_items


TUTOR_PROMPT_TEMPLATE = """
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

TUTOR_PROMPT = LangChainPromptTemplate.from_template(TUTOR_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class TutorAgent:
    def __init__(self):
        self.role = "多模态软件工程答疑老师"
        self.goal = "严格基于课程知识库回答学生问题，并输出结构清晰、层级固定、适合配图展示的答疑内容。"
        self.chain = (TUTOR_PROMPT | SparkLLM() | LangChainStrOutputParser()) if TUTOR_PROMPT is not None and LangChainStrOutputParser is not None else None

    def _fallback_answer(self, question: str, evidence: str) -> str:
        evidence_excerpt = (evidence or "知识库暂未检索到直接材料，请换一种问法或补充关键词。")[:240]
        return f"""## 一、直接回答
根据课程知识库，先给出面向当前问题的结构化回答。{evidence_excerpt}

## 二、图解说明
核心观点：先定位问题关键词，再回到软件工程阶段、产物和关系来理解。
- 需求分析：明确做什么，输出需求规格说明书
- 总体设计：确定系统结构、模块和接口
- 详细设计：细化模块内部逻辑和算法

## 三、易错点
- 不要把“用户需要什么”和“系统怎么组织实现”混为一谈。
- 总体设计关注架构与模块，详细设计关注模块内部细节。

## 四、自测题
请用一句话说明：需求规格说明书为什么是总体设计的输入？"""

    def _is_error_payload(self, text: str) -> bool:
        try:
            data = json.loads(str(text or ""))
        except Exception:
            return False
        return isinstance(data, dict) and data.get("success") is False and bool(data.get("error"))

    def answer(self, question: str) -> dict:
        evidence_items = retrieve_knowledge_items(question, top_k=3)
        evidence = retrieve_knowledge(question, top_k=3)
        variables = {"question": question, "evidence": evidence}
        if self.chain is not None:
            answer = self.chain.invoke(variables)
        else:
            answer = SparkLLM().invoke(TUTOR_PROMPT_TEMPLATE.format(**variables))
        if self._is_error_payload(answer):
            answer = self._fallback_answer(question, evidence)
        return {"answer": answer, "evidence": evidence, "sources": evidence_items}
