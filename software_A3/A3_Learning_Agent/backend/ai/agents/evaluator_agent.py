try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.langchain_adapter import SparkLLM
from ai.langchain_parsers import parse_json_with_fallback
from .base_agent import XunfeiAgentSpec


EVALUATOR_PROMPT_TEMPLATE = """
你是软件工程课程学习效果评估师。请基于题目、学生答案、参考答案和知识点，对学生答案进行评分。

要求：
1. 严格返回 JSON，不要 Markdown，不要解释；
2. score 为 0-100 的整数；
3. feedback 要指出掌握情况、缺失点和下一步建议；
4. knowledge_point 原样返回。

知识点：{knowledge_point}
题目：{question}
参考答案：{reference_answer}
学生答案：{answer}

返回格式：
{{"score": 0, "feedback": "", "knowledge_point": "{knowledge_point}"}}
""".strip()

EVALUATOR_PROMPT = LangChainPromptTemplate.from_template(EVALUATOR_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class EvaluatorAgent:
    def __init__(self):
        self.role = "学习效果评估师"
        self.goal = "根据练习答案、学习行为和画像评估知识掌握度。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["rule_grading", "langchain_prompt", "spark_llm"],
            input_schema="题目 + 学生答案 + 参考答案 + 知识点",
            output_schema="分数 + 反馈 + 掌握度建议",
        )
        self.chain = (EVALUATOR_PROMPT | SparkLLM() | LangChainStrOutputParser()) if EVALUATOR_PROMPT is not None and LangChainStrOutputParser is not None else None

    def grade(self, question: str, answer: str, reference_answer: str = "", knowledge_point: str = "软件工程基础") -> dict:
        fallback = self._rule_grade(question, answer, reference_answer, knowledge_point)
        variables = {
            "knowledge_point": knowledge_point,
            "question": question,
            "reference_answer": reference_answer or question,
            "answer": answer,
        }
        try:
            if self.chain is not None:
                raw = self.chain.invoke(variables)
            else:
                raw = SparkLLM().invoke(EVALUATOR_PROMPT_TEMPLATE.format(**variables))
            data = parse_json_with_fallback(raw)
            score = int(data.get("score", fallback["score"]))
            score = max(0, min(100, score))
            feedback = str(data.get("feedback") or fallback["feedback"])
            return {"score": score, "feedback": feedback, "knowledge_point": str(data.get("knowledge_point") or knowledge_point)}
        except Exception:
            return fallback

    def _rule_grade(self, question: str, answer: str, reference_answer: str = "", knowledge_point: str = "软件工程基础") -> dict:
        answer_text = str(answer or "").strip()
        reference = str(reference_answer or question or "").strip()
        keyword_pool = [
            "需求", "需求分析", "用户", "业务规则", "系统边界", "规格说明", "总体设计", "架构", "模块", "接口",
            "详细设计", "编码", "测试", "维护", "生命周期", "可行性", "数据流", "用例", "质量", "验证",
        ]
        keywords = [word for word in keyword_pool if word in reference + question + knowledge_point]
        hit = sum(1 for word in keywords if word in answer_text)
        if not answer_text:
            score = 0
        elif keywords:
            score = min(100, max(40, int(hit / len(keywords) * 100)))
        else:
            score = 75 if len(answer_text) >= 20 else 55
        if score >= 85:
            feedback = "回答较完整，能够抓住软件工程概念边界和应用场景，可进入下一阶段学习。"
        elif score >= 60:
            feedback = "回答基本正确，但概念边界、阶段产物或案例映射还需加强，建议复习相关教材片段。"
        else:
            feedback = "回答不够充分，建议重新学习该知识点，重点补充定义、输入输出、阶段产物和典型案例。"
        return {"score": score, "feedback": feedback, "knowledge_point": knowledge_point}
