from .base_agent import XunfeiAgentSpec


class EvaluatorAgent:
    def __init__(self):
        self.role = "学习效果评估师"
        self.goal = "根据练习答案、学习行为和画像评估知识掌握度。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["rule_grading", "spark_chat"],
            input_schema="题目 + 学生答案 + 参考答案 + 知识点",
            output_schema="分数 + 反馈 + 掌握度建议",
        )

    def grade(self, question: str, answer: str, reference_answer: str = "", knowledge_point: str = "机器学习基础") -> dict:
        answer_text = str(answer or "").strip()
        reference = str(reference_answer or question or "").strip()
        keywords = [word for word in ["监督", "无监督", "标签", "分类", "回归", "聚类", "降维", "训练"] if word in reference + question]
        hit = sum(1 for word in keywords if word in answer_text)
        if not answer_text:
            score = 0
        elif keywords:
            score = min(100, max(40, int(hit / len(keywords) * 100)))
        else:
            score = 75 if len(answer_text) >= 20 else 55
        if score >= 85:
            feedback = "回答较完整，能够抓住核心概念，可进入下一阶段学习。"
        elif score >= 60:
            feedback = "回答基本正确，但概念边界还需加强，建议复习相关教材片段。"
        else:
            feedback = "回答不够充分，建议重新学习该知识点并完成基础练习。"
        return {"score": score, "feedback": feedback, "knowledge_point": knowledge_point}
