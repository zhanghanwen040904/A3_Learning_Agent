import json
import re

from ai.langchain_parsers import parse_json_with_fallback
from ai.llm_adapter import PlatformLLM
from config import config
from .base_agent import AgentSpec

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
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["rule_grading", "llm_chat"],
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

    def _extract_reference_choice_answer(self, reference: str) -> tuple[str, str]:
        reference = str(reference or "").strip()
        match = re.match(r"^\s*([A-H]+)\s*[：:]\s*(.+?)\s*$", reference)
        if match:
            return match.group(1).strip().upper(), match.group(2).strip()
        letters = re.findall(r"[A-H]", reference.upper())
        if letters and len(reference) <= 8:
            return "".join(letters), ""
        return "", ""

    def _normalize_choice_answer(self, answer: str) -> str:
        return "".join(re.findall(r"[A-H]", str(answer or "").upper()))

    def _grade_objective(
        self,
        answer_text: str,
        reference: str,
        knowledge_point: str,
        explanation: str,
        common_mistake: str,
        scoring_points: list,
        feedback_correct: str = "",
        feedback_wrong: str = "",
    ) -> dict:
        reference_code, reference_text = self._extract_reference_choice_answer(reference)
        normalized_answer = self._normalize_text(answer_text)
        normalized_reference_text = self._normalize_text(reference_text)
        answer_code = self._normalize_choice_answer(answer_text)

        exact_code_match = bool(reference_code and answer_code == reference_code)
        exact_text_match = bool(reference_text and normalized_answer == normalized_reference_text)
        inclusive_text_match = bool(reference_text and normalized_reference_text and normalized_reference_text in normalized_answer)

        if exact_code_match or exact_text_match or inclusive_text_match:
            score = 100
            is_correct = True
            feedback = feedback_correct or "回答正确，客观题答案命中。"
            matched_keywords = [reference_code or reference_text or knowledge_point]
            missed_keywords = []
            weak_reason = "当前题目回答正确，可以继续下一题。"
        else:
            score = 0
            is_correct = False
            feedback = feedback_wrong or "回答不正确，客观题需要准确作答。"
            matched_keywords = []
            missed_keywords = [reference_code or reference_text or knowledge_point]
            weak_reason = f"当前题目未正确命中客观题答案：{reference_code or reference_text or knowledge_point}"

        return {
            "score": score,
            "is_correct": is_correct,
            "feedback": feedback,
            "knowledge_point": knowledge_point,
            "reference_answer": reference,
            "explanation": explanation or "这是一道客观题，作答时应直接锁定正确选项或标准答案内容。",
            "common_mistake": common_mistake or "常见问题是只凭印象作答，没有准确对应到标准选项。",
            "scoring_points": scoring_points,
            "matched_keywords": matched_keywords,
            "missed_keywords": missed_keywords,
            "weak_reason": weak_reason,
        }

    def _personalize_analysis(
        self,
        base_result: dict,
        question: str,
        answer: str,
        reference: str,
        knowledge_point: str,
        original_explanation: str = "",
        original_common_mistake: str = "",
    ) -> dict:
        if config.MOCK_AI:
            return base_result
        try:
            prompt = f"""
你是一名严谨的课程学习评估老师。请根据题目、学生作答和参考答案，生成有针对性的判题反馈。

要求：
1. 不能只是复述参考答案或题库解析。
2. 必须指出学生答案具体答到了什么、漏了什么、为什么扣分。
3. 解析要围绕学生答案与参考答案的差距展开。
4. 如果学生只写了很短或无关内容，要明确说明问题。
5. score 必须由你根据学生答案质量给出 0-100 分，不要照抄系统初判；系统初判只作为参考。
6. 只输出 JSON，不要 markdown。

输出格式：
{{
  "score": 0,
  "is_correct": false,
  "feedback": "一句总体反馈",
  "explanation": "结合学生答案的针对性解析，说明哪些点对、哪些点缺失、应该如何补充",
  "common_mistake": "本题暴露出的易错点或理解偏差",
  "weak_reason": "形成薄弱点记录的一句话原因",
  "missed_keywords": ["遗漏点1"],
  "matched_keywords": ["命中点1"]
}}

知识点：{knowledge_point}
题目：{question}
学生答案：{answer}
参考答案：{reference}
题库原解析：{original_explanation}
题库原易错点：{original_common_mistake}
系统初判：{json.dumps(base_result, ensure_ascii=False)}
""".strip()
            data = parse_json_with_fallback(PlatformLLM().invoke(prompt))
            if not isinstance(data, dict):
                return base_result
            result = dict(base_result)
            try:
                if data.get("score") is not None:
                    result["score"] = max(0, min(100, int(float(data.get("score")))))
                    result["is_correct"] = bool(data.get("is_correct", result["score"] >= 70))
            except Exception:
                pass
            for key in ["feedback", "explanation", "common_mistake", "weak_reason"]:
                value = str(data.get(key) or "").strip()
                if value:
                    result[key] = value
            for key in ["missed_keywords", "matched_keywords"]:
                value = data.get(key)
                if isinstance(value, list):
                    result[key] = [str(item).strip() for item in value if str(item).strip()][:8]
            return result
        except Exception:
            return base_result

    def grade(
        self,
        question: str,
        answer: str,
        reference_answer: str = "",
        knowledge_point: str = "机器学习基础",
        explanation: str = "",
        common_mistake: str = "",
        scoring_points: list | None = None,
        question_type: str = "",
        feedback_correct: str = "",
        feedback_wrong: str = "",
    ) -> dict:
        answer_text = str(answer or "").strip()
        reference = str(reference_answer or question or "").strip()
        scoring_points = scoring_points or []
        question_type = str(question_type or "").strip().lower()

        if question_type in {"单选题", "多选题", "判断题", "single_choice", "multiple_choice", "true_false"}:
            base_result = self._grade_objective(
                answer_text,
                reference,
                knowledge_point,
                explanation,
                common_mistake,
                scoring_points,
                feedback_correct,
                feedback_wrong,
            )
            return self._personalize_analysis(base_result, question, answer_text, reference, knowledge_point, explanation, common_mistake)

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

        base_result = {
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
        return self._personalize_analysis(base_result, question, answer_text, reference, knowledge_point, explanation, common_mistake)

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
