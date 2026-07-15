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

STRUCTURED_ANALYSIS_PHASES = [
    ("问题定义", ["问题定义", "定义问题", "澄清用户", "真正的问题", "系统规模", "系统目标", "目标报告", "报告书", "成本上限", "投资回收期"]),
    ("可行性研究", ["可行性研究", "可行性", "现有系统", "人工系统", "系统流程图", "高层数据流图", "可选方案", "成本效益", "成本/效益", "效益分析"]),
    ("需求分析", ["需求分析", "数据流图", "DFD", "分层数据流图", "细化数据流图", "自顶向下", "逐层分解", "输出端回溯"]),
]

SUBJECTIVE_CONCEPT_GROUPS = [
    ("问题定义", ["问题定义", "定义问题", "澄清用户", "真正的问题", "系统规模", "系统目标", "目标报告", "报告书", "成本上限", "投资回收期"]),
    ("可行性研究", ["可行性研究", "可行性", "现有系统", "人工系统", "系统流程图", "高层数据流图", "可选方案", "成本效益", "成本/效益", "效益分析"]),
    ("需求分析/DFD", ["需求分析", "数据流图", "DFD", "分层数据流图", "细化数据流图", "自顶向下", "逐层分解", "输出端回溯"]),
    ("数据字典", ["数据字典", "数据元素", "数据流", "数据存储", "字典卡片"]),
    ("加工/算法说明", ["IPO", "黑盒", "加工说明", "关键算法", "工资计算", "工资核算", "报表统计", "审核流程"]),
    ("用户访谈和资料收集", ["访谈", "调研", "财务科", "人事科", "会计", "出纳", "纸质资料", "单据"]),
    ("需求规格和评审", ["软件需求规格说明书", "需求规格", "技术审查", "管理复审", "复审"]),
]

RELATIONSHIP_CONCEPT_GROUPS = [
    ("情景是状态图中的一条路径", ["一条路径", "路径", "示例执行路径", "执行路径", "通过部分或全部状态图"]),
    ("情景描述某个典型行为", ["典型行为", "单一", "具体", "典型", "局部实例", "某个行为", "一条完整动作序列"]),
    ("状态图描述所有可能行为", ["所有行为", "所有可能", "全部生命周期", "全局全集", "所有状态", "所有状态转换", "所有动作序列", "全部合法动作流程"]),
    ("情景受状态图约束或可验证状态图", ["验证", "解释", "遵循", "约束", "状态流转规则", "合法动作流程"]),
]

PHONE_DICTIONARY_CONCEPT_GROUPS = [
    ("电话号码分为校内和校外", ["电话号码", "校内号码", "校外号码", "校内", "校外", "|", "或"]),
    ("校内号码为首位非 0 的 4 位数字", ["校内号码", "校内", "非0", "非 0", "不是0", "不是 0", "3{数字}", "4位", "4 位"]),
    ("校外号码先拨 0 并区分本地/外地", ["校外号码", "校外", "先拨0", "先拨 0", "0+", "本地号码", "本市电话", "外地号码", "外地电话"]),
    ("本地号码为首位非 0 的 8 位号码", ["本地号码", "本市电话", "非0", "非 0", "不是0", "不是 0", "7{数字}", "8位", "8 位"]),
    ("外地号码包含 3 位区码和 8 位外线号", ["外地号码", "外地电话", "区码", "3{数字}", "3位", "3 位", "8位", "8 位", "外线号"]),
    ("定义非 0 数字和普通数字取值范围", ["非0数字", "非 0 数字", "1|2|3|4|5|6|7|8|9", "数字", "0|1|2|3|4|5|6|7|8|9"]),
    ("使用数据字典定义符号", ["=", "|", "[", "]", "{", "}", "定义", "选择", "重复"]),
]

DFD_MODELING_CONCEPT_GROUPS = [
    ("识别数据源点和终点", ["文件管理员", "源点", "终点", "外部实体", "修改报告"]),
    ("识别主要处理功能", ["接收修改信息", "读主文件", "校核记录", "修改原始记录", "产生报告", "生成修改报告", "更新记录"]),
    ("识别核心数据存储", ["修改信息", "主文件", "修改后的主文件", "新文件", "磁盘", "数据存储"]),
    ("区分逻辑处理和实现细节", ["按记录号排序", "穿孔卡片", "读卡片", "具体实现", "不必", "逻辑处理"]),
    ("体现分层数据流图", ["0层", "顶层", "一层", "功能级", "分层", "子加工", "细化"]),
    ("说明错误记录处理", ["校验码", "校核", "出错", "丢掉", "剔除", "错误记录"]),
]

GENERIC_KNOWLEDGE_LABELS = {"习题", "练习", "题目", "综合题", "软件工程", "未分类"}


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

    def _is_empty_or_no_knowledge_answer(self, answer: str) -> bool:
        text = self._normalize_text(answer)
        if not text:
            return True
        if len(text) <= 1:
            return True
        no_answer_exact = {
            "不知道", "不会", "不清楚", "没学", "不会做", "不懂", "不知道答案", "随便", "不知道怎么写",
            "idontknow", "dontknow", "unknown", "noidea",
        }
        if text in no_answer_exact:
            return True
        no_answer_patterns = ["不知道", "不会", "不清楚", "没学", "不懂", "noidea", "dontknow", "unknown"]
        return len(text) <= 12 and any(pattern in text for pattern in no_answer_patterns)

    def _important_term_hits(self, answer: str, keywords: list[str], reference: str, knowledge_point: str) -> list[str]:
        answer_norm = self._normalize_text(answer)
        terms = []
        for item in [knowledge_point, *keywords, *DOMAIN_KEYWORDS]:
            item_text = str(item or "").strip()
            item_norm = self._normalize_text(item_text)
            if len(item_norm) >= 2 and item_text not in terms:
                terms.append(item_text)
        for token in re.findall(r"[一-龥A-Za-z0-9]{2,}", str(reference or "")):
            if 2 <= len(token) <= 12 and token not in terms:
                terms.append(token)
            if len(terms) >= 24:
                break
        return [term for term in terms if self._normalize_text(term) and self._normalize_text(term) in answer_norm]

    def _is_clearly_unrelated_answer(self, answer: str, reference: str, keywords: list[str], knowledge_point: str) -> bool:
        if self._is_empty_or_no_knowledge_answer(answer):
            return True
        answer_text = str(answer or "").strip()
        reference_text = str(reference or "").strip()
        if not reference_text:
            return False
        if self._score_subjective_concepts(answer_text, reference_text)[1]:
            return False
        important_hits = self._important_term_hits(answer_text, keywords, reference_text, knowledge_point)
        unit_ratio = self._unit_coverage_ratio(answer_text, reference_text)
        char_ratio = self._char_overlap_ratio(answer_text, reference_text)
        if not important_hits and unit_ratio <= 0 and char_ratio < 0.08:
            return True
        if len(important_hits) <= 1 and unit_ratio <= 0 and char_ratio < 0.25 and len(answer_text) <= 14:
            return True
        if len(answer_text) <= 4 and not important_hits:
            return True
        return False

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

    def _contains_any_term(self, text: str, terms: list[str]) -> bool:
        normalized_text = self._normalize_text(text)
        for term in terms:
            normalized_term = self._normalize_text(term)
            if normalized_term and normalized_term in normalized_text:
                return True
        return False

    def _score_subjective_concepts(self, answer: str, reference: str, question: str = "") -> tuple[int, list[str], list[str]]:
        rubric_source = "\n".join([str(question or ""), str(reference or "")])
        group_sets = [SUBJECTIVE_CONCEPT_GROUPS]
        is_relationship_reference = self._contains_any_term(rubric_source, ["情景", "状态图", "所有行为", "动作序列"])
        if is_relationship_reference:
            group_sets.append(RELATIONSHIP_CONCEPT_GROUPS)
        is_phone_dictionary_reference = self._contains_any_term(rubric_source, ["电话号码", "校内电话", "校外电话", "本市电话", "本地电话", "外地电话", "区码", "数据字典"])
        if is_phone_dictionary_reference:
            group_sets.append(PHONE_DICTIONARY_CONCEPT_GROUPS)
        is_dfd_modeling_reference = self._contains_any_term(rubric_source, ["数据流图", "dfd", "主文件", "修改信息", "文件管理员", "修改报告"])
        if is_dfd_modeling_reference:
            group_sets.append(DFD_MODELING_CONCEPT_GROUPS)

        relevant_groups = []
        for group_set in group_sets:
            relevant_groups.extend(
                (label, terms)
                for label, terms in group_set
                if self._contains_any_term(rubric_source, terms)
            )
        min_groups = 2 if (is_relationship_reference or is_phone_dictionary_reference or is_dfd_modeling_reference) else 3
        if len(relevant_groups) < min_groups:
            return 0, [], []

        matched = []
        missed = []
        for label, terms in relevant_groups:
            if self._contains_any_term(answer, terms):
                matched.append(label)
            else:
                missed.append(label)

        coverage = len(matched) / max(len(relevant_groups), 1)
        if coverage >= 0.99:
            score = 94
        elif coverage >= 0.85:
            score = 86
        elif coverage >= 0.70:
            score = 76
        elif coverage >= 0.55:
            score = 66
        elif coverage >= 0.40:
            score = 55
        elif coverage >= 0.20:
            score = 35
        else:
            score = 0

        required_phases = [
            (label, terms)
            for label, terms in STRUCTURED_ANALYSIS_PHASES
            if self._contains_any_term(reference, terms)
        ]
        if len(required_phases) >= 3:
            phase_hits = sum(1 for _, terms in required_phases if self._contains_any_term(answer, terms))
            if phase_hits == 0:
                score = min(score, 55)
            elif phase_hits == 1:
                score = min(score, 68)
            elif phase_hits == 2:
                score = min(score, 82)

        return score, matched, missed

    def _build_targeted_explanation(
        self,
        answer: str,
        score: int,
        matched_keywords: list[str],
        missed_keywords: list[str],
        scoring_points: list,
    ) -> str:
        matched = [str(item).strip() for item in matched_keywords if str(item).strip()]
        missed = [str(item).strip() for item in missed_keywords if str(item).strip()]
        scoring = [str(item).strip() for item in scoring_points if str(item).strip()]

        parts = []
        if matched:
            parts.append(f"你的答案已经答到了{'、'.join(matched[:5])}。")
        else:
            parts.append("你的答案没有明显命中参考答案中的核心要点。")

        if missed:
            parts.append(f"主要扣分点在于缺少{'、'.join(missed[:5])}。")
        elif score < 90:
            parts.append("虽然主要要点已有覆盖，但个别表述还可以更贴近参考答案的关键词。")
        else:
            parts.append("关键要点覆盖较完整，扣分主要来自表述细节或术语精确度。")

        if scoring:
            parts.append(f"对照得分点，还需要补足：{'；'.join(scoring[:3])}。")

        if score < 60:
            parts.append("因此当前答案只能算零散命中，还没有完整回答题目要求。")
        elif score < 75:
            parts.append("因此当前答案属于部分正确，但关键关系或必要说明覆盖还不足。")
        elif score < 90:
            parts.append("因此当前答案基本正确，但还需要补齐遗漏要点或把关系表述得更精确。")
        else:
            parts.append("整体已经接近标准答案，后续只需进一步精确化术语和表述。")

        return "".join(parts)

    def _looks_like_reference_restatement(self, explanation: str, reference: str) -> bool:
        explanation_norm = self._normalize_text(explanation)
        reference_norm = self._normalize_text(reference)
        if len(explanation_norm) < 30 or len(reference_norm) < 30:
            return False
        if explanation_norm in reference_norm or reference_norm in explanation_norm:
            return True
        overlap = len(set(explanation_norm) & set(reference_norm)) / max(len(set(explanation_norm)), 1)
        return overlap > 0.92 and not any(term in explanation for term in ["你的答案", "主要扣分", "缺少", "漏", "命中", "答到了"])

    def _extract_reference_choice_answer(self, reference: str) -> tuple[str, str]:
        reference = str(reference or "").strip()
        cleaned = re.sub(r"^\s*(?:答案|参考答案|正确答案|标准答案)\s*[：:：是为]?\s*", "", reference)
        choice_chars = "A-HＡ-Ｈ"
        match = re.match(rf"^\s*(?:选项)?\s*([{choice_chars}]+)\s*[\.\．、：:\)]\s*(.+?)\s*$", cleaned, flags=re.IGNORECASE)
        if match:
            return self._normalize_choice_answer(match.group(1)), match.group(2).strip()
        match = re.search(rf"(?:答案|参考答案|正确答案|标准答案|选|为|是)\s*[：:：]?\s*([{choice_chars}]+)", reference[:32], flags=re.IGNORECASE)
        if match:
            return self._normalize_choice_answer(match.group(1)), cleaned
        letters = re.findall(rf"[{choice_chars}]", cleaned.upper())
        if letters and len(cleaned) <= 12:
            return self._normalize_choice_answer("".join(letters)), ""
        return "", ""

    def _normalize_choice_answer(self, answer: str) -> str:
        fullwidth_map = str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH")
        text = str(answer or "").upper().translate(fullwidth_map)
        return "".join(re.findall(r"[A-H]", text))

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
        answer_code = self._normalize_choice_answer(answer_text)
        if not reference_code:
            reference_head = str(reference or "").strip()[:64]
            reference_head = re.sub(
                r"^\s*(?:答案|参考答案|正确答案|标准答案|answer|答案为|参考答案为)\s*[:：是为]?\s*",
                "",
                reference_head,
                flags=re.IGNORECASE,
            )
            reference_match = re.match(r"^\s*([A-HＡ-Ｈ])(?:\s*[\.\．、:：\)]|\s+|$)", reference_head, flags=re.IGNORECASE)
            if reference_match:
                reference_code = self._normalize_choice_answer(reference_match.group(1))
                reference_text = str(reference or "").strip()
        if not reference_code:
            reference_match = re.search(r"([A-HＡ-Ｈ])\s*[\.\．、:：\)]", str(reference or "").strip()[:64], flags=re.IGNORECASE)
            if reference_match:
                reference_code = self._normalize_choice_answer(reference_match.group(1))
                reference_text = str(reference or "").strip()
        if not answer_code:
            answer_match = re.search(r"\b([A-HＡ-Ｈ])\b", str(answer_text or ""), flags=re.IGNORECASE)
            if answer_match:
                answer_code = self._normalize_choice_answer(answer_match.group(1))

        exact_code_match = bool(reference_code and answer_code == reference_code)

        if exact_code_match:
            score = 100
            is_correct = True
            feedback = feedback_correct or f"回答正确，标准答案是 {reference_code}。"
            matched_keywords = [reference_code or reference_text or knowledge_point]
            missed_keywords = []
            weak_reason = "当前题目回答正确，可以继续下一题。"
        else:
            score = 0
            is_correct = False
            feedback = feedback_wrong or f"回答不正确，客观题按标准答案精确判分；标准答案是 {reference_code or reference_text or reference}。"
            matched_keywords = []
            missed_keywords = [reference_code or reference_text or knowledge_point]
            weak_reason = f"当前题目未正确命中客观题答案：{reference_code or reference_text or knowledge_point}"
            force_zero = True

        return {
            "score": score,
            "is_correct": is_correct,
            "feedback": feedback,
            "knowledge_point": knowledge_point,
            "reference_answer": reference,
            "explanation": explanation or f"这是一道客观题，系统直接对照标准答案判分。你的答案是“{answer_text or '未作答'}”，标准答案是“{reference_code or reference_text or reference}”。",
            "common_mistake": common_mistake or "常见问题是没有准确填写标准选项字母，或把相近选项混淆。",
            "scoring_points": scoring_points,
            "matched_keywords": matched_keywords,
            "missed_keywords": missed_keywords,
            "weak_reason": weak_reason,
            "graded_by": "rule_objective",
            "answer_code": answer_code,
            "reference_code": reference_code,
            **({"force_zero": True} if 'force_zero' in locals() and force_zero else {}),
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
        if config.MOCK_AI or base_result.get("force_zero"):
            return base_result
        try:
            prompt = f"""
你是一名严谨的课程学习评估老师。请作为主判老师，独立根据题目、学生作答和参考答案进行评分与解析。

要求：
1. 不能只是复述参考答案或题库解析。
2. 必须指出学生答案具体答到了什么、漏了什么、为什么扣分。
3. 解析要围绕学生答案与参考答案的差距展开，必须直接评价“学生答案”，不要把参考答案重新展示一遍。
4. 以语义等价为最高优先级。只要学生答案与参考答案表达的核心含义、必要条件、约束和结论一致，即使语序不同、术语不同、符号写法不同、表达更口语化或更详细，也应给满分或接近满分。
5. 不要因为没有照抄参考答案、关键词字面不一致、步骤顺序不同、变量名不同、符号格式不同而扣分；只有语义缺失、约束遗漏、结论错误、类型/方向错误、计算错误、对象关系错误时才扣分。
6. 如果学生答案比参考答案更详细，但没有引入错误，应视为正确；多写的合理解释不扣分。
7. 如果学生只写了很短、无关、乱答、答非所问、与参考答案没有实质重合，score 必须给 0。
8. 如果学生答案完全错误，不允许给安慰分、格式分、字数分。
9. score 必须由你根据学生答案质量给出 0-100 分，不要照抄规则兜底结果；规则兜底结果只用于模型异常时的备用参考。
10. 通用评分标准：0=完全错误或无关；1-39=仅有零散相关词但没有有效解释；40-59=有少量正确点但关键内容大多缺失；60-74=部分正确；75-89=基本正确但存在必要约束或关键点遗漏；90-100=语义完整准确。
11. 对形式化定义题、计算题、关系辨析题、设计题，要优先判断约束、步骤、结论是否实质正确，不要只按关键词字面重合评分。
12. 形式化规格说明题应拆分评分，不要因单个约束缺失过度扣分：核心功能逻辑约 40%，输入/输出与类型约 20%，关键约束或状态不变条件约 25%，符号与表达严谨性约 15%。如果学生已经正确表达主逻辑，只遗漏状态不变、边界约束或符号细节，通常应落在 65-85 分区间；只有主逻辑也错误或无法读出规格含义时，才给 60 分以下。
13. 解析必须说明扣分比例依据；如果语义等价，应明确说明“与参考答案语义一致，因此不因表述顺序或写法不同扣分”。
14. 只输出 JSON，不要 markdown。

输出格式：
{{
  "score": 0,
  "is_correct": false,
  "feedback": "一句总体反馈",
  "explanation": "针对学生答案的语义评价：先判断是否与参考答案语义等价，再说明答到了什么、是否遗漏必要点、为什么给这个分数；禁止整段复述参考答案",
  "common_mistake": "本题暴露出的易错点或理解偏差",
  "weak_reason": "形成薄弱点记录的一句话原因",
  "missed_keywords": ["遗漏点1"],
  "matched_keywords": ["命中点1"],
  "deduction_reason": "扣分原因和扣分幅度依据；如果语义等价则写明不扣分"
}}

知识点：{knowledge_point}
题目：{question}
学生答案：{answer}
参考答案：{reference}
题库原解析：{original_explanation}
题库原易错点：{original_common_mistake}
规则兜底结果：{json.dumps(base_result, ensure_ascii=False)}
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
                    if key == "explanation" and self._looks_like_reference_restatement(value, reference):
                        continue
                    result[key] = value
            deduction_reason = str(data.get("deduction_reason") or "").strip()
            if deduction_reason:
                result["deduction_reason"] = deduction_reason
                result["weak_reason"] = deduction_reason
            for key in ["missed_keywords", "matched_keywords"]:
                value = data.get(key)
                if value is None:
                    alias = "missed_points" if key == "missed_keywords" else "matched_points"
                    value = data.get(alias)
                if isinstance(value, list):
                    result[key] = [str(item).strip() for item in value if str(item).strip()][:8]
            result["graded_by"] = "llm"
            result["rule_fallback"] = base_result
            return result
        except Exception as exc:
            base_result["graded_by"] = "rule_fallback"
            base_result["llm_error"] = str(exc)
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
            return self._grade_objective(
                answer_text,
                reference,
                knowledge_point,
                explanation,
                common_mistake,
                scoring_points,
                feedback_correct,
                feedback_wrong,
            )

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
                score = 55
            elif blended_ratio >= 0.2:
                score = 25
            else:
                score = 0
        else:
            score = 30 if len(answer_text) >= 20 else 0

        concept_score, concept_matched, concept_missed = self._score_subjective_concepts(answer_text, reference, question)
        if concept_score > score:
            score = concept_score
            matched_keywords = list(dict.fromkeys([*matched_keywords, *concept_matched]))
            missed_keywords = concept_missed[:8]

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
            "explanation": self._build_targeted_explanation(answer_text, score, matched_keywords, missed_keywords, scoring_points),
            "common_mistake": common_mistake or "常见问题是只写结论，不解释原因，也没有说明与相近概念的区别。",
            "scoring_points": scoring_points,
            "matched_keywords": matched_keywords,
            "missed_keywords": missed_keywords,
            "weak_reason": (
                f"当前答案缺少关键点：{'、'.join(missed_keywords[:4])}"
                if missed_keywords
                else "当前答案已覆盖主要关键点，可以继续做更高阶题目。"
            ),
            "graded_by": "rule_fallback",
        }
        return self._personalize_analysis(base_result, question, answer_text, reference, knowledge_point, explanation, common_mistake)

    def _extract_keywords(self, reference: str, knowledge_point: str, scoring_points: list) -> list[str]:
        result = []
        clean_point = str(knowledge_point or "").split("/")[-1].strip()
        clean_point = re.sub(r"^\d+\s*", "", clean_point)
        clean_point = re.sub(r"^\d+[\.、]\s*", "", clean_point)
        if clean_point and clean_point not in GENERIC_KNOWLEDGE_LABELS and clean_point not in result:
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
