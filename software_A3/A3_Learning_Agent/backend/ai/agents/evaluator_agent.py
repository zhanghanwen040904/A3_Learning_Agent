import re

from .base_agent import XunfeiAgentSpec

DOMAIN_KEYWORDS = [
    "人工智能",
    "机器学习",
    "深度学习",
    "监督学习",
    "无监督学习",
    "强化学习",
    "分类",
    "回归",
    "聚类",
    "降维",
    "训练集",
    "验证集",
    "测试集",
    "准确率",
    "召回率",
    "精确率",
    "F1值",
    "过拟合",
    "欠拟合",
    "决策树",
    "神经网络",
    "PCA",
    "K-Means",
    "需求分析",
    "可行性研究",
    "软件生命周期",
    "总体设计",
    "详细设计",
    "单元测试",
]


class EvaluatorAgent:
    def __init__(self):
        self.role = "学习效果评估师"
        self.goal = "根据题目、学生答案和参考答案判断掌握程度，并输出结构化判题结果。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["rule_grading", "spark_chat"],
            input_schema="题目 + 学生答案 + 参考答案 + 知识点 + 解析信息",
            output_schema="分数 + 正误 + 反馈 + 参考答案 + 解析 + 易错点 + 得分点",
        )

    def _normalize_text(self, text: str) -> str:
        text = str(text or "").strip()
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("；", ";").replace("，", ",").replace("：", ":")
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"[、,;:。！？!?\(\)\[\]\"'“”‘’]", "", text)
        return text.lower()

    def _split_units(self, text: str) -> list[str]:
        parts = re.split(r"[；;，,\n。！？!?]", str(text or ""))
        units = []
        for part in parts:
            normalized = self._normalize_text(part)
            if len(normalized) >= 2:
                units.append(normalized)
        return units

    def _char_overlap_ratio(self, answer: str, reference: str) -> float:
        answer_chars = set(self._normalize_text(answer))
        reference_chars = set(self._normalize_text(reference))
        if not answer_chars or not reference_chars:
            return 0.0
        return len(answer_chars & reference_chars) / len(reference_chars)

    def _unit_coverage_ratio(self, answer: str, reference: str) -> float:
        answer_norm = self._normalize_text(answer)
        ref_units = self._split_units(reference)
        if not answer_norm or not ref_units:
            return 0.0
        matched = 0
        for unit in ref_units:
            if unit in answer_norm:
                matched += 1
                continue
            if len(set(unit) & set(answer_norm)) / max(len(set(unit)), 1) >= 0.7:
                matched += 1
        return matched / len(ref_units)

    def grade(
        self,
        question: str,
        answer: str,
        reference_answer: str = "",
        knowledge_point: str = "机器学习基础",
        explanation: str = "",
        common_mistake: str = "",
        scoring_points: list | None = None,
    ) -> dict:
        answer_text = str(answer or "").strip()
        reference = str(reference_answer or question or "").strip()
        scoring_points = scoring_points or []

        normalized_answer = self._normalize_text(answer_text)
        normalized_reference = self._normalize_text(reference)
        keywords = self._extract_keywords(reference, knowledge_point, scoring_points)
        matched_keywords = [word for word in keywords if self._normalize_text(word) and self._normalize_text(word) in normalized_answer]
        missed_keywords = [word for word in keywords if self._normalize_text(word) and self._normalize_text(word) not in normalized_answer]
        keyword_ratio = len(matched_keywords) / max(len(keywords), 1) if keywords else 0.0
        unit_ratio = self._unit_coverage_ratio(answer_text, reference)
        char_ratio = self._char_overlap_ratio(answer_text, reference)

        if not answer_text:
            score = 0
        elif normalized_reference and normalized_answer == normalized_reference:
            score = 100
            matched_keywords = keywords[:]
            missed_keywords = []
        elif normalized_reference and normalized_reference in normalized_answer:
            score = 95
            matched_keywords = keywords[:]
            missed_keywords = []
        elif keywords:
            blended_ratio = max(keyword_ratio, unit_ratio * 0.75 + char_ratio * 0.25)
            if blended_ratio >= 0.9:
                score = 92
            elif blended_ratio >= 0.75:
                score = 84
            elif blended_ratio >= 0.6:
                score = 74
            elif blended_ratio >= 0.4:
                score = 60
            else:
                score = 40
        else:
            score = 75 if len(answer_text) >= 20 else 55

        is_correct = score >= 70
        if score >= 90:
            feedback = "回答非常完整，已经准确覆盖参考要点。"
        elif score >= 75:
            feedback = "回答基本正确，核心知识点已经覆盖。"
        elif score >= 60:
            feedback = "回答部分正确，但还有关键要点没有展开。"
        else:
            feedback = "回答不够充分，建议先回到知识点原文重新梳理。"

        return {
            "score": score,
            "is_correct": is_correct,
            "feedback": feedback,
            "knowledge_point": knowledge_point,
            "reference_answer": reference,
            "explanation": explanation or "建议结合教材原文，从定义、特点和应用三个角度重新组织答案。",
            "common_mistake": common_mistake or "常见问题是只写结论，不解释原因，也没有说明与相近概念的区别。",
            "scoring_points": scoring_points,
            "matched_keywords": matched_keywords,
            "missed_keywords": missed_keywords,
            "weak_reason": (
                f"当前答案缺少关键点：{'、'.join(missed_keywords[:4])}"
                if missed_keywords
                else "当前答案已覆盖主要关键点，可以继续做更高阶题目。"
            ),
        }

    def _extract_keywords(self, reference: str, knowledge_point: str, scoring_points: list) -> list[str]:
        result = []
        clean_point = str(knowledge_point or "").split("/")[-1].strip()
        clean_point = re.sub(r"^\d+\s*", "", clean_point)
        clean_point = re.sub(r"^\d+[\.、]\s*", "", clean_point)
        if clean_point and clean_point not in result:
            result.append(clean_point)

        for keyword in DOMAIN_KEYWORDS:
            if keyword in reference and keyword not in result:
                result.append(keyword)
            if len(result) >= 6:
                return result[:6]

        for point in scoring_points:
            point = str(point or "")
            point = re.sub(r"^(先准确说明|回答中明确提到|能结合|表述时体现出|不要只列名词).*?[“\"]?", "", point)
            point = point.strip("”\"这一关键内容。的基本定义。 ")
            point = re.sub(r"^\d+[\.、]\s*", "", point)
            if 2 <= len(point) <= 16 and point not in result:
                result.append(point)
            if len(result) >= 6:
                break

        return result[:6]
